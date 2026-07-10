from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes.detect_route import router as detect_router

app = FastAPI(
    title="আলোক (Alok)",
    description="Assistive vision API: detects Bangladeshi banknotes and everyday "
                "objects, and generates spatial Bangla announcements for blind and "
                "low-vision users.",
)

# Allow any origin so the PWA also works if hosted separately from the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def revalidate_static(request, call_next):
    """Make browsers revalidate app files on every load (cheap 304s), so
    updates reach users immediately; offline is the service worker's job."""
    response = await call_next(request)
    if not request.url.path.startswith("/detect"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.get("/api")
def api_status():
    return {"message": "Backend is running successfully!"}


# Include YOLO detection routes
app.include_router(detect_router, prefix="/detect", tags=["Detection"])

# Serve the frontend (landing page, live mode, money counter, help) at /
# Mounted last so /detect, /api, and /docs keep priority.
_frontend_candidates = [
    Path(__file__).parent.parent / "frontend",  # repo layout: backend/ + frontend/
    Path(__file__).parent / "frontend",         # flat layout (e.g. Docker image)
]
for _dir in _frontend_candidates:
    if _dir.is_dir():
        app.mount("/", StaticFiles(directory=str(_dir), html=True), name="frontend")
        break
