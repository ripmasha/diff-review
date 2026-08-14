from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import enforce_content_length, require_bearer
from app.api.routes import public_routes, reviews

public_router = APIRouter()
public_router.include_router(public_routes.public_router)

v1_router = APIRouter(
    prefix="/v1",
    dependencies=[Depends(require_bearer), Depends(enforce_content_length)],
)
v1_router.include_router(reviews.router)
