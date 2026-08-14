from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    uptimeSeconds: float


class Limits(BaseModel):
    maxPayloadBytes: int
    chunkBytes: int
    maxConcurrentJobs: int
    rateLimitPerMinute: int


class SpecResponse(BaseModel):
    specVersion: str
    providers: list[str]
    limits: Limits
