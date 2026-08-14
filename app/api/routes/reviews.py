from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/reviews")
async def create_review() -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/reviews/{job_id}")
async def get_review(job_id: str) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/reviews/{job_id}/stream")
async def stream_review(job_id: str) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
