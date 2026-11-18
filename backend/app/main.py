# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import events, ingest, prune

app = FastAPI(title="NatCatDashboard API")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    # The browser frontend only ever reads. Write endpoints are called
    # server-side with X-Admin-Token, never from a browser.
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)

app.include_router(ingest.router)
app.include_router(events.router)
app.include_router(prune.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
