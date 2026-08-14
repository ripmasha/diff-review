import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import public_router, v1_router
from app.core.config import VERSION, get_settings
from app.core.errors import (
    http_exception_handler,
    unhandled_error_handler,
    validation_error_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    get_settings()
    app.state.started_at = time.monotonic()
    yield


app = FastAPI(title="diff-review", version=VERSION, lifespan=lifespan)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(public_router)
app.include_router(v1_router)
