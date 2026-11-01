"""
Admin endpoints: every account, its live usage, and the controls.

    GET   /api/admin/users              every account with its usage this month (the dashboard polls this)
    PATCH /api/admin/users/{user_id}    change one account: its monthly token quota, blocked or active, admin or not

Rules the code keeps (so the admin cannot lock everyone out by mistake)
    - An admin cannot block themselves or remove their own admin role.
    - The last active admin cannot be blocked or demoted.
    - Blocking an account signs it out everywhere at once (its sessions are deleted).
    - A quota of 0 means "no limit".
"""

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import DbDep
from app.auth.access import AdminDep
from app.auth.quota import month_start, usage_by_owner
from app.db import users_repo
from app.models.user import User, UserChange, UserUsage

router = APIRouter(prefix="/admin", tags=["admin"])


async def _working_owners(db, request: Request) -> set[str]:
    running = request.app.state.workflow.running_runs()
    if not running:
        return set()
    marks = ",".join("?" for _ in running)
    cursor = await db.execute(
        f"SELECT DISTINCT projects.owner_id AS owner FROM runs JOIN projects ON projects.id = runs.project_id WHERE runs.id IN ({marks})",
        tuple(running),
    )
    return {row["owner"] for row in await cursor.fetchall() if row["owner"]}


def _usage(user: User, totals: dict[str, int], working: set[str]) -> UserUsage:
    tokens = totals.get("tokens", 0)
    quota = user.monthly_token_quota
    return UserUsage(
        user=user, tokens=tokens, llm_calls=totals.get("llm", 0), decision_calls=totals.get("jev", 0),
        github_calls=totals.get("github", 0), runs=totals.get("runs", 0), projects=totals.get("projects", 0),
        working=user.id in working, quota_left=max(0, quota - tokens) if quota else None,
    )


@router.get("/users")
async def all_users(admin: AdminDep, db: DbDep, request: Request) -> list[UserUsage]:
    totals = await usage_by_owner(db, month_start())
    working = await _working_owners(db, request)
    return [_usage(user, totals.get(user.id, {}), working) for user in await users_repo.list_users(db)]


@router.patch("/users/{user_id}")
async def change_user(user_id: str, change: UserChange, admin: AdminDep, db: DbDep, request: Request) -> UserUsage:
    target = await users_repo.get_user(db, user_id)
    fields = change.model_dump(exclude_unset=True)
    demoting = fields.get("role") == "user" and target.role == "admin"
    blocking = fields.get("status") == "blocked" and target.status == "active"
    if target.id == admin.id and (demoting or blocking):
        raise HTTPException(status_code=409, detail="You cannot block yourself or remove your own admin role.")
    if (demoting or blocking) and target.role == "admin" and await users_repo.count_admins(db) <= 1:
        raise HTTPException(status_code=409, detail="This is the last admin; make someone else admin first.")
    if "monthly_token_quota" in fields:
        fields["monthly_token_quota"] = fields["monthly_token_quota"] or None  # 0 = no limit
    user = await users_repo.change_user(db, user_id, fields)
    if blocking:
        await users_repo.end_all_sessions(db, user_id)
    totals = await usage_by_owner(db, month_start())
    return _usage(user, totals.get(user.id, {}), await _working_owners(db, request))
