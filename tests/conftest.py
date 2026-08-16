import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token-do-not-use-in-production"


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    os.environ["SERVICE_TOKEN"] = TOKEN

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_singletons():
    from app.core.jobs import get_job_store
    from app.core.ratelimit import get_rate_limiter

    store = get_job_store()
    store._jobs.clear()
    store._cache_index.clear()
    store._idempotency_index.clear()

    bucket = get_rate_limiter()
    bucket._tokens = bucket._capacity

    yield


def assert_envelope(response, code: str) -> None:
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["message"]
