import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.deps import enforce_content_length
from app.core.cachekey import compute_cache_key
from app.core.config import PROVIDERS
from app.core.diffparse import DiffParseError, parse_unified_diff
from app.core.jobs import Job, get_job_store
from app.core.ratelimit import get_rate_limiter
from app.core.worker import process_job
from app.schemas.reviews import (
    JobStatus,
    ReviewCreateResponse,
    ReviewRequest,
    ReviewResult,
    Usage,
)

router = APIRouter()

_STREAM_POLL_SECONDS = 0.05


async def enforce_rate_limit() -> None:
    allowed, retry_after = await get_rate_limiter().try_acquire()
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded, retry later",
            headers={"Retry-After": str(max(1, int(retry_after) + 1))},
        )


@router.post(
    "/reviews",
    status_code=202,
    response_model=ReviewCreateResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(enforce_content_length)],
)
async def create_review(request: Request) -> ReviewCreateResponse:
    raw_body = await request.body()

    store = get_job_store()
    body_hash = hashlib.sha256(raw_body).hexdigest()
    idem_key = request.headers.get("idempotency-key")

    if idem_key:
        existing = await store.find_by_idempotency_key(idem_key)
        if existing is not None:
            existing_hash, existing_job_id = existing
            if existing_hash != body_hash:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key reused with a different body",
                )
            return ReviewCreateResponse(jobId=existing_job_id, status=JobStatus.QUEUED)

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Body is not valid JSON")

    try:
        review_request = ReviewRequest.model_validate(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed request body")

    diff_text = review_request.diff
    if diff_text is None or diff_text.strip() == "":
        raise HTTPException(
            status_code=422, detail="diff is required and must not be empty"
        )

    try:
        parse_unified_diff(diff_text)
    except DiffParseError:
        raise HTTPException(
            status_code=422, detail="diff is not a parseable unified diff"
        )

    provider = review_request.options.provider
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=400, detail=f"options.provider must be one of {PROVIDERS}"
        )
    max_findings = review_request.options.maxFindings

    cache_key = compute_cache_key(diff_text, provider, max_findings)
    cached = await store.find_by_cache_key(cache_key)
    job_id = uuid.uuid4().hex

    if cached is not None:
        job = Job(job_id=job_id, status=JobStatus.QUEUED, source_job_id=cached.job_id)
        await store.create(job, idempotency_key=idem_key, body_hash=body_hash)
        return ReviewCreateResponse(jobId=job_id, status=JobStatus.QUEUED)

    job = Job(job_id=job_id, status=JobStatus.QUEUED)
    await store.create(job, idempotency_key=idem_key, body_hash=body_hash)
    asyncio.create_task(process_job(job_id, diff_text, provider, max_findings))

    return ReviewCreateResponse(jobId=job_id, status=JobStatus.QUEUED)


def _usage_with_cache_hit(usage: Usage | None, cache_hit: bool) -> Usage | None:
    if usage is None:
        return None
    return usage.model_copy(update={"cacheHit": cache_hit})


def _payload_with_cache_hit(event_type: str, payload: dict, cache_hit: bool) -> dict:
    if event_type != "done" or not cache_hit:
        return payload
    return {**payload, "usage": {**payload["usage"], "cacheHit": True}}


def _is_terminal(event_type: str, payload: dict) -> bool:
    """A successful job ends with the `done` event, a failed one with a
    `status` event carrying the error; there is no `done` on failure."""
    if event_type == "done":
        return True
    return event_type == "status" and payload.get("status") == JobStatus.FAILED.value


@router.get("/reviews/{job_id}", response_model=ReviewResult)
async def get_review(job_id: str) -> ReviewResult:
    resolved = await get_job_store().resolve(job_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Unknown jobId")

    source, cache_hit = resolved
    return ReviewResult(
        jobId=job_id,
        status=source.status,
        findings=source.findings,
        usage=_usage_with_cache_hit(source.usage, cache_hit),
        error=source.error,
    )


async def require_job(job_id: str) -> None:
    """Runs before the streaming response starts; raising from the generator
    itself would be too late to still produce a 404."""
    if await get_job_store().resolve(job_id) is None:
        raise HTTPException(status_code=404, detail="Unknown jobId")


@router.get(
    "/reviews/{job_id}/stream",
    response_class=EventSourceResponse,
    dependencies=[Depends(require_job)],
)
async def stream_review(job_id: str) -> AsyncIterable[ServerSentEvent]:
    store = get_job_store()
    emitted = 0

    while True:
        source, cache_hit = await store.resolve(job_id)
        pending = source.events[emitted:]
        emitted += len(pending)

        for event_type, payload in pending:
            yield ServerSentEvent(
                event=event_type,
                data=_payload_with_cache_hit(event_type, payload, cache_hit),
            )
            if _is_terminal(event_type, payload):
                return

        await asyncio.sleep(_STREAM_POLL_SECONDS)
