import re

from app.core.chunker import DiffChunk
from app.core.diffparse import FileDiff
from app.providers.base import ProviderResult
from app.schemas.reviews import Category, Finding, Severity

_CRED_RE = re.compile(
    r"(api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", re.I
)
_SQL_KEYWORDS = r"\b(SELECT|INSERT|UPDATE|DELETE)\b"
_SQL_CONCAT_RE = re.compile(
    rf"['\"][^'\"]*{_SQL_KEYWORDS}[^'\"]*['\"]\s*\+|\+\s*['\"][^'\"]*{_SQL_KEYWORDS}[^'\"]*['\"]",
    re.I,
)
_NULL_RE = re.compile(r"(==|!=)\s*null")
_INJ_RE = re.compile(
    r"ignore previous instructions|disregard all prior|you are now", re.I
)

_LINE_RULES = [
    ("MOCK-001", Severity.CRITICAL, Category.SECURITY, "eval usage",
     lambda line: "eval(" in line),
    ("MOCK-002", Severity.CRITICAL, Category.SECURITY, "hardcoded credential",
     lambda line: bool(_CRED_RE.search(line))),
    ("MOCK-003", Severity.HIGH, Category.SECURITY, "SQL string concatenation",
     lambda line: bool(_SQL_CONCAT_RE.search(line))),
    ("MOCK-005", Severity.MEDIUM, Category.CORRECTNESS, "loose null comparison",
     lambda line: bool(_NULL_RE.search(line))),
    ("MOCK-006", Severity.MEDIUM, Category.PERFORMANCE, "deep-clone via JSON",
     lambda line: "JSON.parse(JSON.stringify(" in line),
    ("MOCK-007", Severity.LOW, Category.STYLE, "console.log left in",
     lambda line: "console.log(" in line),
    ("MOCK-008", Severity.LOW, Category.STYLE, "unresolved marker",
     lambda line: "TODO" in line or "FIXME" in line),
    ("MOCK-INJ", Severity.CRITICAL, Category.SECURITY, "prompt-injection content",
     lambda line: bool(_INJ_RE.search(line))),
]


def _make_finding(
    rule_id: str, path: str, line: int, severity: Severity, category: Category,
    title: str, evidence: str,
) -> Finding:
    return Finding(
        id=f"{rule_id}:{path}:{line}",
        ruleId=rule_id,
        path=path,
        line=line,
        severity=severity,
        category=category,
        title=title,
        evidence=evidence,
    )


def _scan_empty_catch(f: FileDiff) -> list[Finding]:
    findings: list[Finding] = []
    lines = f.added_lines
    i = 0
    while i < len(lines):
        if re.search(r"\bcatch\b", lines[i].text):
            catch_line = lines[i]
            if re.search(r"\{\s*\}\s*$", catch_line.text.strip()):
                is_empty = True
            else:
                j = i + 1
                body_has_code = False
                closed = False
                while j < len(lines):
                    stripped = lines[j].text.strip()
                    if stripped == "}":
                        closed = True
                        break
                    if stripped and not stripped.startswith("//"):
                        body_has_code = True
                    j += 1
                is_empty = closed and not body_has_code
            if is_empty:
                findings.append(_make_finding(
                    "MOCK-004", f.path, catch_line.line_no,
                    Severity.HIGH, Category.CORRECTNESS,
                    "swallowed exception", catch_line.text,
                ))
        i += 1
    return findings


def _scan_file(f: FileDiff) -> list[Finding]:
    findings: list[Finding] = []
    for added in f.added_lines:
        for rule_id, severity, category, title, predicate in _LINE_RULES:
            if predicate(added.text):
                findings.append(_make_finding(
                    rule_id, f.path, added.line_no, severity, category,
                    title, added.text,
                ))
    findings.extend(_scan_empty_catch(f))
    return findings


async def run(chunks: list[DiffChunk], max_findings: int) -> ProviderResult:
    all_findings: list[Finding] = []
    for chunk in chunks:
        for f in chunk.files:
            all_findings.extend(_scan_file(f))

    seen: set[str] = set()
    deduped: list[Finding] = []
    for finding in all_findings:
        if finding.id not in seen:
            seen.add(finding.id)
            deduped.append(finding)

    deduped.sort(key=lambda f: (f.path, f.line, f.ruleId))
    return ProviderResult(findings=deduped[:max_findings])
