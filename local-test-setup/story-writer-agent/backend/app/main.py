from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import StoryRequest, StoryResponse
from app.services.story_service import run_story_pipeline

app = FastAPI(title="Story Writer Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/stories", response_model=StoryResponse)
async def create_story(request: StoryRequest):
    try:
        return await run_story_pipeline(request.title, request.recipient_email)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Story generation failed: {exc}") from exc
