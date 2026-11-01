"""
Opening a connection to the SQLite database.

What this file does
    One function, `open_connection`, used everywhere a connection is needed.
    It makes sure the data folder exists and switches on the two options
    every connection should have.

How it plugs in
    app/api/deps.py opens one connection per HTTP request.
    app/db/migrations.py opens one at start-up.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


@asynccontextmanager
async def open_connection(database_path: Path):
    """Open the database, hand out the connection, and always close it.

    LEARNING NOTE: asynccontextmanager
      It lets a function be used as  `async with open_connection(path) as db:`
      The code before `yield` runs on the way in, the code after it on the
      way out, even if an error happened in between. That guarantees the
      connection is closed.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = await aiosqlite.connect(database_path)
    try:
        # Rows behave like dictionaries: row["name"] instead of row[1].
        connection.row_factory = aiosqlite.Row
        # LEARNING NOTE: SQLite only enforces REFERENCES rules (foreign keys)
        #   when this is switched on, and it must be done on every connection.
        await connection.execute("PRAGMA foreign_keys = ON")
        yield connection
    finally:
        await connection.close()
