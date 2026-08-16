from typing import Protocol

from app.core.chunker import DiffChunk
from app.schemas.reviews import Finding


class ProviderResult:
    def __init__(self, findings: list[Finding], error: str | None = None) -> None:
        self.findings = findings
        self.error = error


class Provider(Protocol):
    async def run(
        self, chunks: list[DiffChunk], max_findings: int
    ) -> ProviderResult: ...
