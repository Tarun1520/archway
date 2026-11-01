"""
Lesson 11: SQLite (a database in a single file)
===============================================

What you learn here
    - SQLite is a full SQL database that lives in ONE file. No server to
      install or run, which suits a local-first app.
    - The four everyday operations: create a table, insert, read, update.
    - Why values go in through "?" placeholders, never by gluing text.
    - The same thing in async style with aiosqlite.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/11_sqlite_basics.py

    The lesson uses ":memory:", a throwaway database that exists only while
    the script runs, so no file is created.

Where Archway uses this
    backend/app/db/ stores projects, briefs, evidence and receipts in SQLite.
    LangGraph's checkpointer (Lesson 04) also writes to SQLite, in tables it
    creates and manages itself.
"""

import asyncio
import sqlite3

import aiosqlite

CREATE_TABLE = """
CREATE TABLE projects (
    id      INTEGER PRIMARY KEY,   -- a unique number per row, filled in for us
    name    TEXT NOT NULL,         -- NOT NULL: this column must have a value
    status  TEXT NOT NULL,
    license TEXT                   -- may be NULL, which means "unknown"
)
"""


def demo_sync() -> None:
    print("PART 1: sqlite3 (built into Python)")
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row  # lets us read columns by name
    connection.execute(CREATE_TABLE)

    # LEARNING NOTE: always use "?" placeholders.
    #   The "?" marks where a value goes; the values travel separately. Never
    #   build SQL with f-strings: text typed by a user could then be run as
    #   SQL (an attack called "SQL injection").
    connection.execute(
        "INSERT INTO projects (name, status, license) VALUES (?, ?, ?)",
        ("Notes app", "draft", None),  # None is stored as NULL
    )
    connection.execute(
        "INSERT INTO projects (name, status, license) VALUES (?, ?, ?)",
        ("License auditor", "researching", "MIT"),
    )
    connection.execute("UPDATE projects SET status = ? WHERE name = ?", ("researching", "Notes app"))
    connection.commit()  # make the changes permanent

    for row in connection.execute("SELECT id, name, status, license FROM projects ORDER BY id"):
        print(f"  #{row['id']} {row['name']:16} status={row['status']:12} license={row['license']!r}")

    # A hostile "name" is stored as harmless text because it was a parameter.
    hostile = "x'); DROP TABLE projects; --"
    connection.execute("INSERT INTO projects (name, status) VALUES (?, ?)", (hostile, "draft"))
    count = connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"  after inserting a hostile name the table still exists, with {count} rows")
    connection.close()


async def demo_async() -> None:
    print("\nPART 2: aiosqlite (same database, async style)")
    # LEARNING NOTE: why a second library?
    #   FastAPI handles many requests at once using async code (Lesson 09).
    #   A plain sqlite3 call would freeze every request while it waits for the
    #   disk. aiosqlite runs the database work on the side so others continue.
    async with aiosqlite.connect(":memory:") as connection:
        await connection.execute(CREATE_TABLE)
        await connection.execute(
            "INSERT INTO projects (name, status) VALUES (?, ?)", ("Knowledge base", "draft")
        )
        await connection.commit()
        async with connection.execute("SELECT name, status FROM projects") as cursor:
            print("  rows:", await cursor.fetchall())


if __name__ == "__main__":
    demo_sync()
    asyncio.run(demo_async())
