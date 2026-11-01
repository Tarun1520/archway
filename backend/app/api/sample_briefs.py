"""
Sample briefs endpoint (DEMO DATA).

    GET /api/sample-briefs   the sample briefs from backend/fixtures/briefs/

Every item carries "demo": true so the UI can label it as demo data.
"""

from fastapi import APIRouter

from app.samples.briefs import SampleBrief, load_sample_briefs

router = APIRouter(tags=["samples"])


@router.get("/sample-briefs")
async def sample_briefs() -> list[SampleBrief]:
    return load_sample_briefs()
