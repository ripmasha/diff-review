import pytest

from tests.conftest import TOKEN, assert_envelope

V1_PATHS = [
    "/v1/reviews",
    "/v1/reviews/some-job-id",
    "/v1/reviews/some-job-id/stream",
    "/v1/nonexistent",
]
METHODS = ["get", "post", "put", "patch", "delete"]

REJECTED_HEADERS = [
    pytest.param({}, id="no-header"),
    pytest.param({"Authorization": ""}, id="empty-header"),
    pytest.param({"Authorization": "Bearer"}, id="scheme-only"),
    pytest.param({"Authorization": "Bearer "}, id="empty-token"),
    pytest.param({"Authorization": "Bearer wrong-token"}, id="wrong-token"),
    pytest.param({"Authorization": TOKEN}, id="token-without-scheme"),
    pytest.param({"Authorization": f"Basic {TOKEN}"}, id="wrong-scheme"),
]


@pytest.mark.parametrize("path", V1_PATHS)
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("headers", REJECTED_HEADERS)
def test_v1_rejects_requests_without_a_valid_token(client, method, path, headers):
    """If the Authorization header is missing, malformed, or wrong, returns 401."""
    response = getattr(client, method)(path, headers=headers)

    assert response.status_code == 401
    assert_envelope(response, "unauthorized")


@pytest.mark.parametrize("path", V1_PATHS)
@pytest.mark.parametrize("method", METHODS)
def test_v1_accepts_a_valid_token(client, auth, method, path):
    """If authenticated with a valid token, does not return 401."""
    response = getattr(client, method)(path, headers=auth)

    assert response.status_code != 401


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER", "BeArEr"])
def test_bearer_scheme_is_case_insensitive(client, scheme):
    """If the Bearer scheme is in any letter case, still does not return 401."""
    response = client.get("/v1/reviews", headers={"Authorization": f"{scheme} {TOKEN}"})

    assert response.status_code != 401
