from dataclasses import dataclass

from app.core.diffparse import FileDiff, ParsedDiff


@dataclass
class DiffChunk:
    files: list[FileDiff]


def chunk_diff(parsed: ParsedDiff, chunk_bytes: int) -> list[DiffChunk]:
    chunks: list[DiffChunk] = []
    current: list[FileDiff] = []
    current_size = 0

    for f in parsed.files:
        size = len(f.raw_text.encode("utf-8"))

        if size > chunk_bytes:
            if current:
                chunks.append(DiffChunk(files=current))
                current, current_size = [], 0
            chunks.append(DiffChunk(files=[f]))
            continue

        if current and current_size + size > chunk_bytes:
            chunks.append(DiffChunk(files=current))
            current, current_size = [], 0

        current.append(f)
        current_size += size

    if current:
        chunks.append(DiffChunk(files=current))

    return chunks
