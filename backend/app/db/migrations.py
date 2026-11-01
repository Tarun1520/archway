"""
Migrations: creating and upgrading the database tables.

What this file does
    Looks at the numbered .sql files in app/db/sql/ and applies, in order,
    every one the database has not seen yet.

How the database remembers
    SQLite has a built-in number called `user_version` (it starts at 0).
    After applying 0001_initial.sql we set it to 1, and so on. On the next
    start we only run files with a higher number.

How to change the database later
    Add a NEW file, e.g. app/db/sql/0002_add_briefs.sql. Never edit a file
    that has already been applied: existing databases would not get the edit.

How it plugs in
    app/main.py calls `apply_migrations` once when the server starts.
"""

import logging
from pathlib import Path

import aiosqlite

SQL_FOLDER = Path(__file__).parent / "sql"
logger = logging.getLogger("archway.db")


def find_migrations() -> list[tuple[int, Path]]:
    """Return (number, file) pairs sorted by number, e.g. [(1, .../0001_initial.sql)]."""
    found = []
    for file in SQL_FOLDER.glob("*.sql"):
        number_text = file.name.split("_", 1)[0]  # "0001_initial.sql" -> "0001"
        found.append((int(number_text), file))
    found.sort()

    numbers = [number for number, _ in found]
    if numbers != list(range(1, len(numbers) + 1)):
        raise RuntimeError(f"migration files must be numbered 1, 2, 3 ... without gaps; found {numbers}")
    return found


async def current_version(connection: aiosqlite.Connection) -> int:
    cursor = await connection.execute("PRAGMA user_version")
    row = await cursor.fetchone()
    return int(row[0])


async def apply_migrations(connection: aiosqlite.Connection) -> int:
    """Apply every migration newer than the database's version. Returns the new version."""
    version = await current_version(connection)

    for number, file in find_migrations():
        if number <= version:
            continue  # already applied on an earlier start
        # executescript runs several SQL statements from one piece of text.
        await connection.executescript(file.read_text(encoding="utf-8"))
        # PRAGMA cannot take a "?" placeholder. `number` is an int that we
        # produced ourselves from a file name, never user input, so building
        # this one statement with an f-string is safe.
        await connection.execute(f"PRAGMA user_version = {int(number)}")
        await connection.commit()
        logger.info("applied migration", extra={"fields": {"migration": file.name}})
        version = number

    return version
