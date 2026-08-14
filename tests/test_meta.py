import re

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_health_is_public_and_well_formed(client):
    """If called without a token, /health still returns 200 with the documented shape."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert SEMVER.match(body["version"])
    assert isinstance(body["uptimeSeconds"], (int, float))
    assert body["uptimeSeconds"] >= 0


def test_health_uptime_does_not_go_backwards(client):
    """If called twice, uptimeSeconds never decreases between calls."""
    first = client.get("/health").json()["uptimeSeconds"]
    second = client.get("/health").json()["uptimeSeconds"]

    assert second >= first


def test_spec_matches_contract(client):
    """If called, /spec returns limits that exactly match the declared contract."""
    response = client.get("/spec")

    assert response.status_code == 200
    assert response.json() == {
        "specVersion": "1.0",
        "providers": ["mock", "llm"],
        "limits": {
            "maxPayloadBytes": 1048576,
            "chunkBytes": 65536,
            "maxConcurrentJobs": 4,
            "rateLimitPerMinute": 30,
        },
    }


def test_public_routes_ignore_a_bad_token(client):
    """If a bad token is sent anyway, public routes still return 200, not 401."""
    headers = {"Authorization": "Bearer nonsense"}

    assert client.get("/health", headers=headers).status_code == 200
    assert client.get("/spec", headers=headers).status_code == 200
