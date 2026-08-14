from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "1.0.0"
SPEC_VERSION = "1.0"
PROVIDERS = ("mock", "llm")

MAX_PAYLOAD_BYTES = 1048576
CHUNK_BYTES = 65536
MAX_CONCURRENT_JOBS = 4
RATE_LIMIT_PER_MINUTE = 30
RATE_LIMIT_BURST = RATE_LIMIT_PER_MINUTE


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_token: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
