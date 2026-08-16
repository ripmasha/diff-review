from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_bearer
from app.api.routes import public_routes, reviews

public_router = APIRouter()
public_router.include_router(public_routes.public_router)

v1_router = APIRouter(
    prefix="/v1",
    dependencies=[Depends(require_bearer)],
)
v1_router.include_router(reviews.router)


@v1_router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def v1_catch_all(full_path: str) -> None:
    """Ensures every /v1/* request (any path, any method) matches a route
    within this router, so require_bearer runs before Starlette would
    otherwise 404/405 an unmatched path or method without checking auth."""
    raise HTTPException(status_code=404, detail="Not found")
