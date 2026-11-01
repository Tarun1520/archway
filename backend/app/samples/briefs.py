"""
Sample briefs: ready-made ProjectBriefs for demos, tests and evaluation.

What this file does
    Reads every .json file in backend/fixtures/briefs/ and checks each one
    against the ProjectBrief contract.

Why they exist
    IMPLEMENTATION_GUIDE.md section 11 asks for six to eight briefs that each
    provoke a specific situation (a missing license, conflicting
    requirements, weak evidence ...). They let us test the whole system
    without calling a model.

IMPORTANT: this is demo data
    Every sample carries "demo": true so the UI and exports can label it.

How it plugs in
    app/api/sample_briefs.py returns them; tests round-trip them.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from app.models.brief import ProjectBrief
from app.models.common import ArchwayModel

# .../backend/fixtures/briefs  (this file is backend/app/samples/briefs.py)
BRIEFS_FOLDER = Path(__file__).resolve().parents[2] / "fixtures" / "briefs"


class SampleBrief(ArchwayModel):
    # Literal[True]: the only accepted value is true. A sample file that
    # forgets to label itself as demo data is rejected.
    demo: Literal[True]
    slug: str = Field(min_length=1)  # short name, same as the file name
    title: str = Field(min_length=1)
    # Which evaluation situation this brief is meant to provoke.
    scenario: str = Field(min_length=1)
    idea: str = Field(min_length=1)  # the free text a user might have typed
    brief: ProjectBrief


def load_sample_briefs(folder: Path = BRIEFS_FOLDER) -> list[SampleBrief]:
    """Load and validate every sample brief, sorted by file name."""
    samples = []
    for file in sorted(folder.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        sample = SampleBrief.model_validate(data)  # raises if the file breaks the contract
        if sample.slug != file.stem:
            raise ValueError(f"{file.name}: slug '{sample.slug}' must match the file name")
        samples.append(sample)
    return samples
