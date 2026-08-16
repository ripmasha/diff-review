import asyncio
from dataclasses import dataclass, field

from app.schemas.reviews import Finding, JobStatus, Usage


@dataclass
class Job:
    job_id: str
    status: JobStatus
    findings: list[Finding] = field(default_factory=list)
    usage: Usage | None = None
    error: str | None = None
    events: list[tuple[str, dict]] = field(default_factory=list)
    source_job_id: str | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._cache_index: dict[str, str] = {}
        self._idempotency_index: dict[str, tuple[str, str]] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        job: Job,
        idempotency_key: str | None,
        body_hash: str,
    ) -> None:
        async with self._lock:
            self._jobs[job.job_id] = job
            if idempotency_key:
                self._idempotency_index.setdefault(
                    idempotency_key, (body_hash, job.job_id)
                )

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def resolve(self, job_id: str) -> tuple[Job, bool] | None:
        """Returns the job whose result should be shown, plus whether the
        requested job was served from cache."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.source_job_id is None:
                return job, False
            return self._jobs[job.source_job_id], True

    async def update(self, job_id: str, **fields) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            for key, value in fields.items():
                setattr(job, key, value)

    async def append_event(self, job_id: str, event_type: str, payload: dict) -> None:
        async with self._lock:
            self._jobs[job_id].events.append((event_type, payload))

    async def find_by_cache_key(self, cache_key: str) -> Job | None:
        async with self._lock:
            job_id = self._cache_index.get(cache_key)
            return self._jobs.get(job_id) if job_id else None

    async def rebind_cache_key(self, cache_key: str, job_id: str) -> None:
        async with self._lock:
            self._cache_index[cache_key] = job_id

    async def find_by_idempotency_key(self, key: str) -> tuple[str, str] | None:
        async with self._lock:
            return self._idempotency_index.get(key)


_store = JobStore()


def get_job_store() -> JobStore:
    return _store
