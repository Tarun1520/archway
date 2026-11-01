"""
Saving and loading chat messages.

How it plugs in
    Called by app/api/messages.py. Uses the `messages` table.
"""

import aiosqlite

from app.db.projects_repo import get_project
from app.models.common import new_id, utc_now
from app.models.message import Message, MessageCreate


async def add_message(connection: aiosqlite.Connection, project_id: str, data: MessageCreate) -> Message:
    await get_project(connection, project_id)  # raises NotFound if the project is missing

    message = Message(
        id=new_id(), project_id=project_id, role=data.role, content=data.content, created_at=utc_now()
    )
    await connection.execute(
        "INSERT INTO messages (id, project_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (message.id, project_id, message.role, message.content, message.created_at.isoformat()),
    )
    # Adding a message counts as activity on the project.
    await connection.execute(
        "UPDATE projects SET updated_at = ? WHERE id = ?", (message.created_at.isoformat(), project_id)
    )
    await connection.commit()
    return message


async def list_messages(connection: aiosqlite.Connection, project_id: str) -> list[Message]:
    """A project's messages, oldest first (the order a chat is read in)."""
    await get_project(connection, project_id)
    # `rowid` is SQLite's hidden insertion counter. It breaks ties when two
    # messages were saved within the same microsecond.
    cursor = await connection.execute(
        "SELECT * FROM messages WHERE project_id = ? ORDER BY created_at, rowid", (project_id,)
    )
    return [Message(**dict(row)) for row in await cursor.fetchall()]
