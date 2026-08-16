import asyncio
import concurrent.futures
import json
import time

import pytest

from tests.conftest import assert_envelope

VALID_DIFF = """\
diff --git a/src/db.ts b/src/db.ts
index 1111111..2222222 100644
--- a/src/db.ts
+++ b/src/db.ts
@@ -1,2 +1,3 @@
 context line
+eval(userInput)
 trailing line
"""


def _wait_for_completion(client, job_id):
    """The POST handler scheduled background processing via asyncio.create_task
    on TestClient's portal event loop; wait for it to finish on that same loop
    instead of spinning up a separate one (the job store's asyncio.Lock is
    bound to whichever loop first uses it)."""
    from app.core.jobs import get_job_store
    from app.schemas.reviews import JobStatus

    async def _wait():
        store = get_job_store()
        for _ in range(200):
            source, _cache_hit = await store.resolve(job_id)
            if source.status in (JobStatus.DONE, JobStatus.FAILED):
                return source
            await asyncio.sleep(0.05)
        source, _cache_hit = await store.resolve(job_id)
        return source

    return client.portal.call(_wait)


def _parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        events.append(
            (
                lines[0].removeprefix("event: "),
                json.loads(lines[1].removeprefix("data: ")),
            )
        )
    return events


def test_create_review_happy_path(client, auth):
    resp = client.post("/v1/reviews", json={"diff": VALID_DIFF}, headers=auth)
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert isinstance(body["jobId"], str) and body["jobId"]


def test_invalid_json_body(client, auth):
    resp = client.post(
        "/v1/reviews",
        content=b"{not valid json",
        headers={**auth, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert_envelope(resp, "invalid_json")


def test_payload_too_large_returns_413(client, auth):
    from app.core.config import MAX_PAYLOAD_BYTES

    oversized_diff = VALID_DIFF + "+" + "x" * MAX_PAYLOAD_BYTES
    resp = client.post("/v1/reviews", json={"diff": oversized_diff}, headers=auth)
    assert resp.status_code == 413
    assert_envelope(resp, "payload_too_large")


def test_invalid_provider_value(client, auth):
    resp = client.post(
        "/v1/reviews",
        json={"diff": VALID_DIFF, "options": {"provider": "gpt5"}},
        headers=auth,
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"diff": ""},
        {"diff": "   "},
        {"diff": "not a diff at all, just prose"},
    ],
)
def test_invalid_diff_returns_422(client, auth, body):
    resp = client.post("/v1/reviews", json=body, headers=auth)
    assert resp.status_code == 422
    assert_envelope(resp, "invalid_diff")


def test_idempotency_same_key_same_body_returns_same_job_id(client, auth):
    headers = {**auth, "Idempotency-Key": "key-1"}
    resp1 = client.post("/v1/reviews", json={"diff": VALID_DIFF}, headers=headers)
    job_id = resp1.json()["jobId"]

    resp2 = client.post("/v1/reviews", json={"diff": VALID_DIFF}, headers=headers)
    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert resp2.json()["jobId"] == job_id


def test_cache_hit_with_different_idempotency_key(client, auth):
    resp1 = client.post(
        "/v1/reviews",
        json={"diff": VALID_DIFF},
        headers={**auth, "Idempotency-Key": "key-a"},
    )
    job1 = resp1.json()["jobId"]
    _wait_for_completion(client, job1)

    resp2 = client.post(
        "/v1/reviews",
        json={"diff": VALID_DIFF},
        headers={**auth, "Idempotency-Key": "key-b"},
    )
    job2 = resp2.json()["jobId"]
    assert job2 != job1

    result = client.get(f"/v1/reviews/{job2}", headers=auth).json()
    assert result["usage"]["cacheHit"] is True


def test_idempotency_same_key_different_body_conflicts(client, auth):
    headers = {**auth, "Idempotency-Key": "key-2"}
    resp1 = client.post("/v1/reviews", json={"diff": VALID_DIFF}, headers=headers)
    assert resp1.status_code == 202

    other_diff = VALID_DIFF.replace("eval(userInput)", "console.log('x')")
    resp2 = client.post("/v1/reviews", json={"diff": other_diff}, headers=headers)
    assert resp2.status_code == 409
    assert_envelope(resp2, "idempotency_conflict")


def test_cache_hit_without_idempotency_key(client, auth):
    resp1 = client.post("/v1/reviews", json={"diff": VALID_DIFF}, headers=auth)
    job1 = resp1.json()["jobId"]
    _wait_for_completion(client, job1)

    resp2 = client.post("/v1/reviews", json={"diff": VALID_DIFF}, headers=auth)
    job2 = resp2.json()["jobId"]
    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert resp2.json()["status"] == "queued"
    assert job2 != job1

    result1 = client.get(f"/v1/reviews/{job1}", headers=auth).json()
    result2 = client.get(f"/v1/reviews/{job2}", headers=auth).json()
    assert result1["usage"]["cacheHit"] is False
    assert result2["usage"]["cacheHit"] is True
    assert result2["jobId"] == job2
    assert result2["findings"] == result1["findings"]


def test_cache_hit_with_default_options_normalized(client, auth):
    resp1 = client.post("/v1/reviews", json={"diff": VALID_DIFF}, headers=auth)
    job1 = resp1.json()["jobId"]
    _wait_for_completion(client, job1)

    resp2 = client.post(
        "/v1/reviews",
        json={"diff": VALID_DIFF, "options": {"provider": "mock", "maxFindings": 100}},
        headers=auth,
    )
    job2 = resp2.json()["jobId"]
    assert job2 != job1

    result2 = client.get(f"/v1/reviews/{job2}", headers=auth).json()
    assert result2["usage"]["cacheHit"] is True


def test_rate_limit_returns_429_with_retry_after(client, auth):
    from app.core.config import RATE_LIMIT_BURST

    for i in range(int(RATE_LIMIT_BURST)):
        diff = VALID_DIFF.replace("db.ts", f"db{i}.ts")
        resp = client.post("/v1/reviews", json={"diff": diff}, headers=auth)
        assert resp.status_code == 202

    resp = client.post(
        "/v1/reviews",
        json={"diff": VALID_DIFF.replace("db.ts", "dbX.ts")},
        headers=auth,
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert_envelope(resp, "rate_limited")


def test_burst_never_returns_5xx(client, auth):
    from app.core.config import RATE_LIMIT_BURST

    request_count = 50

    def _post(i: int):
        diff = VALID_DIFF.replace("db.ts", f"db{i}.ts")
        return client.post("/v1/reviews", json={"diff": diff}, headers=auth)

    with concurrent.futures.ThreadPoolExecutor(max_workers=request_count) as pool:
        responses = list(pool.map(_post, range(request_count)))

    statuses = [r.status_code for r in responses]
    assert all(status in (202, 429) for status in statuses)
    assert statuses.count(202) == int(RATE_LIMIT_BURST)
    assert statuses.count(429) == request_count - int(RATE_LIMIT_BURST)


def test_mock_rule_triggers_and_job_completes(client, auth):
    from app.schemas.reviews import JobStatus

    resp = client.post("/v1/reviews", json={"diff": VALID_DIFF}, headers=auth)
    job_id = resp.json()["jobId"]

    job = _wait_for_completion(client, job_id)
    assert job.status == JobStatus.DONE
    assert len(job.findings) == 1
    finding = job.findings[0]
    assert finding.ruleId == "MOCK-001"
    assert finding.path == "src/db.ts"
    assert finding.evidence == "eval(userInput)"


def test_get_unknown_job_id_returns_404(client, auth):
    resp = client.get("/v1/reviews/does-not-exist", headers=auth)
    assert resp.status_code == 404
    assert_envelope(resp, "not_found")


def test_stream_unknown_job_id_returns_404(client, auth):
    resp = client.get("/v1/reviews/does-not-exist/stream", headers=auth)
    assert resp.status_code == 404
    assert_envelope(resp, "not_found")


def test_stream_of_cached_job_reports_cache_hit(client, auth):
    diff = VALID_DIFF.replace("db.ts", "streamcache.ts")
    job1 = client.post("/v1/reviews", json={"diff": diff}, headers=auth).json()["jobId"]
    _wait_for_completion(client, job1)
    job2 = client.post("/v1/reviews", json={"diff": diff}, headers=auth).json()["jobId"]

    events1 = _parse_sse(client.get(f"/v1/reviews/{job1}/stream", headers=auth).text)
    events2 = _parse_sse(client.get(f"/v1/reviews/{job2}/stream", headers=auth).text)

    assert [name for name, _ in events2] == [name for name, _ in events1]
    assert [d for name, d in events2 if name == "finding"] == [
        d for name, d in events1 if name == "finding"
    ]
    assert events1[-1][1]["usage"]["cacheHit"] is False
    assert events2[-1][1]["usage"]["cacheHit"] is True
