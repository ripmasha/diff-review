import hashlib
import json


def compute_cache_key(diff: str, provider: str, max_findings: int) -> str:
    normalized = json.dumps(
        {"diff": diff, "options": {"provider": provider, "maxFindings": max_findings}},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
