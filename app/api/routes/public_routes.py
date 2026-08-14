import time

from fastapi import APIRouter, Request

from app.core.config import (
    CHUNK_BYTES,
    MAX_CONCURRENT_JOBS,
    MAX_PAYLOAD_BYTES,
    PROVIDERS,
    RATE_LIMIT_PER_MINUTE,
    SPEC_VERSION,
    VERSION,
)
from app.schemas.meta import HealthResponse, Limits, SpecResponse

public_router = APIRouter()


@public_router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=VERSION,
        uptimeSeconds=round(time.monotonic() - request.app.state.started_at, 3),
    )


@public_router.get("/spec", response_model=SpecResponse)
async def spec() -> SpecResponse:
    return SpecResponse(
        specVersion=SPEC_VERSION,
        providers=list(PROVIDERS),
        limits=Limits(
            maxPayloadBytes=MAX_PAYLOAD_BYTES,
            chunkBytes=CHUNK_BYTES,
            maxConcurrentJobs=MAX_CONCURRENT_JOBS,
            rateLimitPerMinute=RATE_LIMIT_PER_MINUTE,
        ),
    )
