from app.core.config import MAX_PAYLOAD_BYTES
from tests.conftest import assert_envelope

OVERSIZED = b"x" * (MAX_PAYLOAD_BYTES + 1)


def test_unknown_v1_path_is_not_found(client, auth):
    """If an authenticated request hits an undefined /v1 path, returns 404 in the envelope."""
    response = client.get("/v1/nope", headers=auth)

    assert response.status_code == 404
    assert_envelope(response, "not_found")


def test_unknown_public_path_is_not_found(client):
    """If a request hits an undefined public path, Starlette's 404 is reshaped into the envelope."""
    response = client.get("/nope")

    assert response.status_code == 404
    assert_envelope(response, "not_found")


def test_oversized_payload_is_rejected(client, auth):
    """If Content-Length exceeds the 1 MiB limit, returns 413 without reading the body."""
    response = client.post("/v1/reviews", headers=auth, content=OVERSIZED)

    assert response.status_code == 413
    assert_envelope(response, "payload_too_large")


def test_payload_at_the_limit_passes_the_size_check(client, auth):
    """If Content-Length equals exactly 1 MiB, the size check does not reject it."""
    response = client.post(
        "/v1/reviews", headers=auth, content=b"x" * MAX_PAYLOAD_BYTES
    )

    assert response.status_code != 413


def test_auth_is_checked_before_payload_size(client):
    """If both the token is missing and the payload is oversized, returns 401, not 413."""
    response = client.post("/v1/reviews", content=OVERSIZED)

    assert response.status_code == 401
    assert_envelope(response, "unauthorized")


def test_malformed_content_length_is_rejected(client, auth):
    """If Content-Length is not a valid integer, returns 400 invalid_json."""
    response = client.post(
        "/v1/reviews", headers={**auth, "Content-Length": "not-a-number"}, content=b"{}"
    )

    assert response.status_code == 400
    assert_envelope(response, "invalid_json")
