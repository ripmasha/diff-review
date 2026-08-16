import secrets

from fastapi import HTTPException, Request

from app.core.config import MAX_PAYLOAD_BYTES, get_settings


def require_bearer(request: Request) -> None:
    header = request.headers.get("authorization")
    if not header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401, detail="Expected 'Authorization: Bearer <token>'"
        )

    if not secrets.compare_digest(token.strip(), get_settings().service_token):
        raise HTTPException(status_code=401, detail="Invalid token")


async def enforce_content_length(request: Request) -> None:
    raw = request.headers.get("content-length")
    if raw is not None:
        try:
            length = int(raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header")

        if length > MAX_PAYLOAD_BYTES:
            raise HTTPException(
                status_code=413, detail=f"Payload exceeds {MAX_PAYLOAD_BYTES} bytes"
            )

    body = await request.body()
    if len(body) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Payload exceeds maximum size")
