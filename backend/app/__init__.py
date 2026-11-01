"""
The Archway backend application package.

LEARNING NOTE: what is a package?
    A folder becomes an importable Python "package" when it contains a file
    named __init__.py. That is why other files can write
    `from app.models.brief import ProjectBrief`.

How the folders fit together (each one has a single job):

    config/   read and check settings from the environment
    models/   the SHAPE of every piece of data (Pydantic contracts)
    db/       saving and loading data in SQLite
    api/      the HTTP endpoints the frontend calls
    events/   demo events for the live-progress stream
    samples/  loader for the sample briefs in backend/fixtures/

Folders that arrive in later phases: graph/ (LangGraph), llm/, research/,
policy/, jev/, promptgen/, export/.
"""

__version__ = "0.1.0"
