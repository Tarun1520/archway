"""
Saving and loading projects.

What this file does
    The five everyday operations for projects: create, list, get, update,
    delete. Each function takes an open connection as its first argument.

How it plugs in
    Called by app/api/projects.py. Uses the `projects` table created by
    app/db/sql/0001_initial.sql.
"""

import aiosqlite

from app.db.errors import NotFound
from app.models.common import new_id, utc_now
from app.models.project import Project, ProjectCreate, ProjectUpdate


def _to_project(row: aiosqlite.Row) -> Project:
    """Turn one database row into a validated Project object.

    LEARNING NOTE: dict(row) gives {"id": ..., "name": ...}; the two stars
    pass those as named arguments. Pydantic converts the date TEXT back into
    real datetime objects and checks everything on the way.
    """
    values = dict(row)
    values.pop("owner_id", None)  # who owns it is checked by the API (app/auth/access.py), not shown in the project
    return Project(**values)


async def create_project(connection: aiosqlite.Connection, data: ProjectCreate, owner_id: str | None = None) -> Project:
    """A new project. `owner_id` is the account it belongs to (None when accounts are switched off)."""
    now = utc_now()
    project = Project(id=new_id(), name=data.name, idea=data.idea, created_at=now, updated_at=now)

    # LEARNING NOTE: the "?" placeholders keep values separate from the SQL
    #   text, which is what prevents SQL injection (LEARNING_GUIDE topic 35).
    await connection.execute(
        "INSERT INTO projects (id, name, idea, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (project.id, project.name, project.idea, owner_id, now.isoformat(), now.isoformat()),
    )
    await connection.commit()
    return project


async def list_projects(connection: aiosqlite.Connection, owner_id: str | None = None) -> list[Project]:
    """Projects, most recently changed first: one account's (owner_id), or all of them (None)."""
    if owner_id is not None:
        cursor = await connection.execute("SELECT * FROM projects WHERE owner_id = ? ORDER BY updated_at DESC", (owner_id,))
        return [_to_project(row) for row in await cursor.fetchall()]
    cursor = await connection.execute("SELECT * FROM projects ORDER BY updated_at DESC")
    return [_to_project(row) for row in await cursor.fetchall()]


async def get_project(connection: aiosqlite.Connection, project_id: str) -> Project:
    cursor = await connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = await cursor.fetchone()
    if row is None:
        raise NotFound("project", project_id)
    return _to_project(row)


async def update_project(connection: aiosqlite.Connection, project_id: str, data: ProjectUpdate) -> Project:
    project = await get_project(connection, project_id)  # raises NotFound if missing
    new_name = data.name if data.name is not None else project.name
    now = utc_now()

    await connection.execute(
        "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
        (new_name, now.isoformat(), project_id),
    )
    await connection.commit()
    return await get_project(connection, project_id)


async def delete_project(connection: aiosqlite.Connection, project_id: str) -> None:
    """Delete a project. Its messages and runs go with it (ON DELETE CASCADE)."""
    await get_project(connection, project_id)  # raises NotFound if missing
    await connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    await connection.commit()
