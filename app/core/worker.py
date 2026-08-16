import asyncio

from app.core.cachekey import compute_cache_key
from app.core.chunker import chunk_diff
from app.core.config import CHUNK_BYTES, MAX_CONCURRENT_JOBS
from app.core.diffparse import parse_unified_diff
from app.core.jobs import get_job_store
from app.providers import llm as llm_provider
from app.providers import mock as mock_provider
from app.schemas.reviews import JobStatus, Usage

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


async def process_job(job_id: str, diff: str, provider: str, max_findings: int) -> None:
    store = get_job_store()
    async with _semaphore:
        await store.update(job_id, status=JobStatus.RUNNING)
        await store.append_event(job_id, "status", {"status": JobStatus.RUNNING.value})

        try:
            parsed = parse_unified_diff(diff)
            chunks = chunk_diff(parsed, CHUNK_BYTES)
            provider_module = mock_provider if provider == "mock" else llm_provider
            result = await provider_module.run(chunks, max_findings)

            if result.error:
                await store.update(job_id, status=JobStatus.FAILED, error=result.error)
                await store.append_event(
                    job_id, "status", {"status": JobStatus.FAILED.value, "error": result.error}
                )
                return

            for finding in result.findings:
                await store.append_event(job_id, "finding", finding.model_dump())

            usage = Usage(
                inputBytes=len(diff.encode("utf-8")), chunks=len(chunks), cacheHit=False
            )
            await store.update(
                job_id, status=JobStatus.DONE, findings=result.findings, usage=usage
            )
            cache_key = compute_cache_key(diff, provider, max_findings)
            await store.rebind_cache_key(cache_key, job_id)
            await store.append_event(job_id, "status", {"status": JobStatus.DONE.value})
            await store.append_event(
                job_id, "done", {"total": len(result.findings), "usage": usage.model_dump()}
            )
        except Exception as exc:
            await store.update(job_id, status=JobStatus.FAILED, error=str(exc))
            await store.append_event(
                job_id, "status", {"status": JobStatus.FAILED.value, "error": str(exc)}
            )
