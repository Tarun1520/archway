"""
Shared dependencies for API routes.

LEARNING NOTE: what is a "dependency" in FastAPI?
    Something a route needs but should not build itself, such as the settings
    or a database connection. A route asks for it by listing it as an
    argument, and FastAPI supplies it:

        async def list_all(db: DbDep): ...

    This is "plug and play": tests can supply a different database without
    changing the route.

How it plugs in
    Route files import `SettingsDep` and `DbDep` from here.
"""

from collections.abc import AsyncIterator
from typing import Annotated

import aiosqlite
from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from app.config.settings import Settings
from app.db.connection import open_connection


def get_app_settings(request: Request) -> Settings:
    """The settings object that create_app() stored on the app at start-up."""
    return request.app.state.settings


async def get_db(request: HTTPConnection) -> AsyncIterator[aiosqlite.Connection]:
    """One database connection for the length of one request.

    LEARNING NOTE: `yield` in a dependency
      Code before `yield` runs before the route; the route gets the value;
      code after it (closing the connection) runs when the response is done.

    It takes an HTTPConnection (the shared parent of a normal request and a WebSocket), so the voice WebSocket can
    use it too.
    """
    settings: Settings = request.app.state.settings
    async with open_connection(settings.database_path) as connection:
        yield connection


# LEARNING NOTE: Annotated[Type, Depends(function)] is a reusable shortcut for
#   "an argument of this Type, supplied by calling this function".
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
DbDep = Annotated[aiosqlite.Connection, Depends(get_db)]
