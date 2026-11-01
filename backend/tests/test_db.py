"""
Tests for the storage layer (app/db/).

Checkpoint 1 item covered here: "Projects survive a backend restart".

LEARNING NOTE: async tests
    These tests are `async def` because the database functions are async.
    pytest-asyncio (switched on by asyncio_mode = auto in pytest.ini) runs
    them inside an event loop for us.
"""

import pytest

from app.db import messages_repo, projects_repo, runs_repo
from app.db.connection import open_connection
from app.db.errors import NotFound
from app.db.migrations import apply_migrations, current_version, find_migrations
from app.models.lifecycle import InvalidTransition, RunStatus
from app.models.message import MessageCreate
from app.models.project import ProjectCreate, ProjectUpdate
from app.models.run import RunStatusChange


@pytest.fixture
async def db(settings):
    """A migrated, empty database in a temporary folder."""
    async with open_connection(settings.database_path) as connection:
        await apply_migrations(connection)
        yield connection


# --- Migrations -------------------------------------------------------------------
async def test_migrations_create_the_tables_and_record_the_version(db):
    assert await current_version(db) == len(find_migrations())
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    tables = [row["name"] for row in await cursor.fetchall()]
    assert {"projects", "messages", "runs"} <= set(tables)


async def test_running_migrations_twice_changes_nothing(db):
    project = await projects_repo.create_project(db, ProjectCreate(name="Keep me"))
    assert await apply_migrations(db) == len(find_migrations())  # second run: nothing to apply
    assert (await projects_repo.get_project(db, project.id)).name == "Keep me"


# --- Surviving a restart ----------------------------------------------------------
async def test_projects_messages_and_runs_survive_a_restart(settings):
    # "First server process": open, write, close.
    async with open_connection(settings.database_path) as connection:
        await apply_migrations(connection)
        project = await projects_repo.create_project(connection, ProjectCreate(name="Notes app", idea="search notes"))
        await messages_repo.add_message(connection, project.id, MessageCreate(content="hello"))
        run = await runs_repo.create_run(connection, project.id, settings)
        # Adding a message updated the project's "last changed" time, so read
        # it again to know exactly what was saved before the restart.
        project = await projects_repo.get_project(connection, project.id)

    # "Restarted server": a brand-new connection. Only the file is shared.
    async with open_connection(settings.database_path) as connection:
        await apply_migrations(connection)
        restored = await projects_repo.get_project(connection, project.id)
        assert restored == project
        assert [m.content for m in await messages_repo.list_messages(connection, project.id)] == ["hello"]
        assert (await runs_repo.get_run(connection, run.id)).status == RunStatus.DRAFT


# --- Projects ---------------------------------------------------------------------
async def test_an_idea_that_was_not_given_stays_none(db):
    project = await projects_repo.create_project(db, ProjectCreate(name="No idea yet"))
    assert (await projects_repo.get_project(db, project.id)).idea is None


async def test_update_list_and_delete_a_project(db):
    first = await projects_repo.create_project(db, ProjectCreate(name="First"))
    second = await projects_repo.create_project(db, ProjectCreate(name="Second"))

    renamed = await projects_repo.update_project(db, first.id, ProjectUpdate(name="First, renamed"))
    assert renamed.name == "First, renamed"
    assert renamed.updated_at >= first.updated_at
    # Most recently changed comes first.
    assert [p.id for p in await projects_repo.list_projects(db)] == [first.id, second.id]

    await projects_repo.delete_project(db, first.id)
    with pytest.raises(NotFound):
        await projects_repo.get_project(db, first.id)


async def test_deleting_a_project_removes_its_messages_and_runs(db, settings):
    project = await projects_repo.create_project(db, ProjectCreate(name="Temporary"))
    await messages_repo.add_message(db, project.id, MessageCreate(content="hi"))
    run = await runs_repo.create_run(db, project.id, settings)

    await projects_repo.delete_project(db, project.id)

    cursor = await db.execute("SELECT COUNT(*) AS n FROM messages")
    assert (await cursor.fetchone())["n"] == 0
    with pytest.raises(NotFound):
        await runs_repo.get_run(db, run.id)


async def test_hostile_text_is_stored_as_plain_text(db):
    """Placeholders keep user text out of the SQL, so this is just a name."""
    hostile = "x'); DROP TABLE projects; --"
    project = await projects_repo.create_project(db, ProjectCreate(name=hostile))
    assert (await projects_repo.get_project(db, project.id)).name == hostile


# --- Messages ---------------------------------------------------------------------
async def test_messages_come_back_oldest_first(db):
    project = await projects_repo.create_project(db, ProjectCreate(name="Chat"))
    for text in ("one", "two", "three"):
        await messages_repo.add_message(db, project.id, MessageCreate(content=text))
    assert [m.content for m in await messages_repo.list_messages(db, project.id)] == ["one", "two", "three"]


async def test_a_message_needs_an_existing_project(db):
    with pytest.raises(NotFound):
        await messages_repo.add_message(db, "no-such-project", MessageCreate(content="hi"))


# --- Runs -------------------------------------------------------------------------
async def test_a_new_run_is_a_draft_and_records_the_service_modes(db, settings):
    project = await projects_repo.create_project(db, ProjectCreate(name="P"))
    run = await runs_repo.create_run(db, project.id, settings)
    assert run.status == RunStatus.DRAFT
    assert run.brief_confirmed is False
    assert (run.jev_mode, run.llm_mode, run.github_mode) == ("fixture", "fixture", "fixture")
    assert run.outcome is None


async def test_research_cannot_start_until_the_brief_is_confirmed(db, settings):
    project = await projects_repo.create_project(db, ProjectCreate(name="P"))
    run = await runs_repo.create_run(db, project.id, settings)

    with pytest.raises(InvalidTransition):
        await runs_repo.change_status(db, run.id, RunStatusChange(status=RunStatus.RESEARCHING))
    assert (await runs_repo.get_run(db, run.id)).status == RunStatus.DRAFT  # unchanged

    await runs_repo.mark_brief_confirmed(db, run.id)
    moved = await runs_repo.change_status(db, run.id, RunStatusChange(status=RunStatus.RESEARCHING))
    assert moved.status == RunStatus.RESEARCHING


async def test_pause_remembers_where_it_came_from_and_resumes_there(db, settings):
    project = await projects_repo.create_project(db, ProjectCreate(name="P"))
    run = await runs_repo.create_run(db, project.id, settings)
    await runs_repo.mark_brief_confirmed(db, run.id)
    await runs_repo.change_status(db, run.id, RunStatusChange(status=RunStatus.RESEARCHING))

    paused = await runs_repo.change_status(db, run.id, RunStatusChange(status=RunStatus.PAUSED))
    assert paused.paused_from == RunStatus.RESEARCHING

    with pytest.raises(InvalidTransition):
        await runs_repo.change_status(db, run.id, RunStatusChange(status=RunStatus.BUILDING_PLAN))

    resumed = await runs_repo.change_status(db, run.id, RunStatusChange(status=RunStatus.RESEARCHING))
    assert resumed.status == RunStatus.RESEARCHING
    assert resumed.paused_from is None


async def test_an_abstention_is_saved_as_completed_with_its_explanation(db, settings):
    project = await projects_repo.create_project(db, ProjectCreate(name="P"))
    run = await runs_repo.create_run(db, project.id, settings)
    await runs_repo.mark_brief_confirmed(db, run.id)
    await runs_repo.change_status(db, run.id, RunStatusChange(status=RunStatus.RESEARCHING))

    finished = await runs_repo.change_status(
        db, run.id,
        RunStatusChange(status=RunStatus.COMPLETED, outcome="abstained", outcome_note="Not enough evidence"),
    )
    assert finished.status == RunStatus.COMPLETED
    assert finished.outcome == "abstained"
    assert finished.outcome_note == "Not enough evidence"
