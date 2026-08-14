import re
from dataclasses import dataclass, field

_GIT_HEADER_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
_OLD_FILE_RE = re.compile(r"^--- (?:a/)?(.+)$")
_NEW_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class DiffParseError(ValueError):
    pass


@dataclass
class AddedLine:
    line_no: int
    text: str


@dataclass
class FileDiff:
    path: str
    raw_text: str
    added_lines: list[AddedLine] = field(default_factory=list)


@dataclass
class ParsedDiff:
    files: list[FileDiff]


def _split_segments(lines: list[str]) -> list[list[str]]:
    boundaries = [i for i, line in enumerate(lines) if _GIT_HEADER_RE.match(line)]
    if boundaries:
        boundaries.append(len(lines))
        return [lines[boundaries[i]:boundaries[i + 1]] for i in range(len(boundaries) - 1)]

    boundaries = [
        i
        for i in range(len(lines) - 1)
        if _OLD_FILE_RE.match(lines[i]) and _NEW_FILE_RE.match(lines[i + 1])
    ]
    if not boundaries:
        return []
    boundaries.append(len(lines))
    return [lines[boundaries[i]:boundaries[i + 1]] for i in range(len(boundaries) - 1)]


def _parse_segment(segment: list[str]) -> FileDiff | None:
    path: str | None = None
    is_deletion = False
    for line in segment:
        match = _NEW_FILE_RE.match(line)
        if match:
            candidate = match.group(1).strip()
            if candidate == "/dev/null":
                is_deletion = True
            else:
                path = candidate
            break

    if path is None and is_deletion:
        for line in segment:
            old_match = _OLD_FILE_RE.match(line)
            if old_match:
                path = old_match.group(1).strip()
                break

    if path is None:
        return None

    added_lines: list[AddedLine] = []
    new_line = 0
    in_hunk = False
    for line in segment:
        hunk_match = _HUNK_RE.match(line)
        if hunk_match:
            new_line = int(hunk_match.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added_lines.append(AddedLine(line_no=new_line, text=line[1:]))
            new_line += 1
        elif line.startswith("-"):
            continue
        elif line.startswith("\\"):
            continue
        else:
            new_line += 1

    return FileDiff(path=path, raw_text="\n".join(segment), added_lines=added_lines)


def parse_unified_diff(text: str) -> ParsedDiff:
    lines = text.splitlines()
    segments = _split_segments(lines)
    if not segments:
        raise DiffParseError("no recognizable file headers found in diff")

    files: list[FileDiff] = []
    for segment in segments:
        has_hunk = any(_HUNK_RE.match(line) for line in segment)
        has_new_file_header = any(_NEW_FILE_RE.match(line) for line in segment)
        if not (has_hunk and has_new_file_header):
            continue
        parsed = _parse_segment(segment)
        if parsed is not None:
            files.append(parsed)

    if not files:
        raise DiffParseError("no valid file diff with a hunk header was found")

    return ParsedDiff(files=files)
