"""
Usage per account, and the monthly token quota.

What this file does
    month_start()                    the first moment of the current calendar month (UTC)
    usage_by_owner(db, since)        per account: model tokens, model / decision / GitHub calls, runs started, projects
    tokens_used(db, user_id)         one account's model tokens this month
    tokens_left(db, user)            what is left of its quota (None = no limit)

Where the numbers come from
    Every call to an outside service is already saved as a usage row on its run (usage_events), with the tokens the
    model reported. A run belongs to a project and a project to an account, so the totals are one query: nothing is
    counted twice and nothing new has to be recorded.

Its honest limit
    Tokens a provider did not report are not counted (rare). Voice requests (Archy) are not counted here yet.
"""

from datetime import datetime, timezone

import aiosqlite

from app.models.user import User


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def usage_by_owner(connection: aiosqlite.Connection, since: datetime) -> dict[str | None, dict[str, int]]:
    """account id -> {"tokens", "llm", "jev", "github", "runs", "projects"} (None = projects with no owner)."""
    totals: dict[str | None, dict[str, int]] = {}

    def entry(owner: str | None) -> dict[str, int]:
        return totals.setdefault(owner, {"tokens": 0, "llm": 0, "jev": 0, "github": 0, "runs": 0, "projects": 0})

    cursor = await connection.execute(
        "SELECT projects.owner_id AS owner, usage_events.service AS service, SUM(usage_events.count) AS calls, "
        "COALESCE(SUM(usage_events.tokens_if_known), 0) AS tokens "
        "FROM usage_events JOIN runs ON runs.id = usage_events.run_id JOIN projects ON projects.id = runs.project_id "
        "WHERE usage_events.timestamp >= ? GROUP BY projects.owner_id, usage_events.service",
        (since.isoformat(),),
    )
    for row in await cursor.fetchall():
        item = entry(row["owner"])
        item[row["service"]] = int(row["calls"])
        if row["service"] == "llm":
            item["tokens"] += int(row["tokens"])
    cursor = await connection.execute(
        "SELECT projects.owner_id AS owner, COUNT(*) AS n FROM runs JOIN projects ON projects.id = runs.project_id "
        "WHERE runs.created_at >= ? GROUP BY projects.owner_id",
        (since.isoformat(),),
    )
    for row in await cursor.fetchall():
        entry(row["owner"])["runs"] = int(row["n"])
    cursor = await connection.execute("SELECT owner_id AS owner, COUNT(*) AS n FROM projects GROUP BY owner_id")
    for row in await cursor.fetchall():
        entry(row["owner"])["projects"] = int(row["n"])
    return totals


async def tokens_used(connection: aiosqlite.Connection, user_id: str) -> int:
    cursor = await connection.execute(
        "SELECT COALESCE(SUM(usage_events.tokens_if_known), 0) AS tokens FROM usage_events "
        "JOIN runs ON runs.id = usage_events.run_id JOIN projects ON projects.id = runs.project_id "
        "WHERE projects.owner_id = ? AND usage_events.service = 'llm' AND usage_events.timestamp >= ?",
        (user_id, month_start().isoformat()),
    )
    return int((await cursor.fetchone())["tokens"])


async def tokens_left(connection: aiosqlite.Connection, user: User) -> int | None:
    if not user.monthly_token_quota:
        return None
    return max(0, user.monthly_token_quota - await tokens_used(connection, user.id))
