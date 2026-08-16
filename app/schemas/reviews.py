from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    SECURITY = "security"
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    STYLE = "style"


class ReviewOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = "mock"
    maxFindings: int = Field(default=100, ge=0)


class ReviewRequest(BaseModel):
    """`diff` is intentionally optional here: malformed JSON/shape should map
    to 400 via the existing validation_error_handler, while a missing/empty/
    unparseable diff is validated by hand in the route and mapped to 422."""

    model_config = ConfigDict(extra="ignore")

    diff: str | None = None
    options: ReviewOptions = Field(default_factory=ReviewOptions)


class ReviewCreateResponse(BaseModel):
    jobId: str
    status: JobStatus


class Finding(BaseModel):
    id: str
    ruleId: str
    path: str
    line: int
    severity: Severity
    category: Category
    title: str
    evidence: str


class Usage(BaseModel):
    inputBytes: int
    chunks: int
    cacheHit: bool


class ReviewResult(BaseModel):
    jobId: str
    status: JobStatus
    findings: list[Finding] = Field(default_factory=list)
    usage: Usage | None = None
    error: str | None = None
