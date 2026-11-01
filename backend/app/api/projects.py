"""
Project endpoints.

    POST   /api/projects            create a project
    GET    /api/projects            list projects
    GET    /api/projects/{id}       get one
    PATCH  /api/projects/{id}       rename it
    DELETE /api/projects/{id}       delete it, with everything that belongs to it

LEARNING NOTE: HTTP methods
    GET reads, POST creates, PATCH changes part of something, DELETE removes.
    Status code 201 means "created"; 204 means "done, nothing to send back".

How it plugs in
    Each route does three small things: receive validated input, call ONE
    repository function, return the result. All SQL lives in app/db/.
"""

import logging

from fastapi import APIRouter, Request, status

from app.api.deps import DbDep
from app.auth.access import UserDep, owner_filter
from app.db import projects_repo, runs_repo
from app.models.project import Project, ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger("archway.api")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, db: DbDep, user: UserDep) -> Project:
    # `data` has already been checked against ProjectCreate by FastAPI. The project belongs to whoever made it.
    project = await projects_repo.create_project(db, data, owner_filter(user))
    # Log the id only. The idea text is the user's private content.
    logger.info("project created", extra={"fields": {"project_id": project.id}})
    return project


@router.get("")
async def list_projects(db: DbDep, user: UserDep) -> list[Project]:
    # Each account sees its own projects (an admin's studio too: the admin dashboard shows everyone's usage).
    return await projects_repo.list_projects(db, owner_filter(user))


@router.get("/{project_id}")
async def get_project(project_id: str, db: DbDep) -> Project:
    return await projects_repo.get_project(db, project_id)


@router.patch("/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate, db: DbDep) -> Project:
    return await projects_repo.update_project(db, project_id, data)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, db: DbDep, request: Request) -> None:
    # Collect the run ids BEFORE deleting: afterwards the rows are gone.
    run_ids = [run.id for run in await runs_repo.list_runs(db, project_id)]

    # Deleting the project also deletes its messages, runs, briefs, usage and
    # events (ON DELETE CASCADE in the SQL files).
    await projects_repo.delete_project(db, project_id)

    # The runs' LangGraph checkpoints are in a separate file; remove them too.
    for run_id in run_ids:
        await request.app.state.workflow.forget_run(run_id)
    logger.info("project deleted", extra={"fields": {"project_id": project_id}})
