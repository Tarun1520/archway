"""
Health check: the simplest possible endpoint.

What this file does
    GET /api/health answers "is the backend running?". Tools and the
    frontend call it to check the server is up.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    version: str


@router.get("/health")
async def health() -> Health:
    return Health(status="ok", version=__version__)
