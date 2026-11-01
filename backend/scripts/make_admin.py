"""
Make an account the admin (or create the admin account), from the terminal.

How to run (from backend/)
    .venv/bin/python scripts/make_admin.py you@example.com

    - If the account exists, it becomes an admin (no quota) and takes over any projects made before accounts existed.
    - If it does not, you are asked for a password (typed into your terminal, never shown, never saved anywhere but as
      a hash) and the admin account is created.

Usually not needed: with ADMIN_EMAIL set in backend/.env, signing up with that email makes the admin automatically.
"""

import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.passwords import hash_password  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.db import users_repo  # noqa: E402
from app.db.connection import open_connection  # noqa: E402
from app.db.migrations import apply_migrations  # noqa: E402
from app.models.user import MIN_PASSWORD  # noqa: E402


async def main(email: str) -> None:
    settings = get_settings()
    async with open_connection(settings.database_path) as db:
        await apply_migrations(db)
        found = await users_repo.user_by_email(db, email)
        if found:
            user, _ = found
            await users_repo.change_user(db, user.id, {"role": "admin", "status": "active", "monthly_token_quota": None})
            print(f"{email} is now an admin.")
        else:
            password = getpass.getpass(f"Choose a password for {email} (at least {MIN_PASSWORD} characters): ")
            if len(password) < MIN_PASSWORD or password != getpass.getpass("Type it again: "):
                sys.exit("The passwords were too short or did not match. Nothing was changed.")
            user = await users_repo.create_user(db, email=email, password_hash=hash_password(password), name=None, role="admin", quota=None)
            print(f"Admin account created for {email}.")
        claimed = await users_repo.claim_unowned_projects(db, user.id)
        if claimed:
            print(f"{claimed} project(s) from before accounts existed now belong to {email}.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        sys.exit("Usage: .venv/bin/python scripts/make_admin.py you@example.com")
    asyncio.run(main(sys.argv[1].strip().lower()))
