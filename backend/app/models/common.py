"""
Small shared pieces used by every model file.

How it plugs in
    Every other file in app/models/ imports from here.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict

# A service is either really called or answered from recorded data.
ServiceMode = Literal["live", "fixture"]


def new_id() -> str:
    """A new unique id, as 32 letters and digits.

    LEARNING NOTE: why a UUID and not 1, 2, 3 ...?
      A UUID can be created anywhere without asking the database "what is the
      next number?". It is practically impossible for two to collide.
    """
    return uuid.uuid4().hex


def utc_now() -> datetime:
    """The current time, in UTC, WITH its timezone attached.

    LEARNING NOTE: always store times in UTC
      A time without a timezone is ambiguous ("10:00 where?"). Storing UTC
      everywhere and converting only for display avoids a whole class of bugs.
    """
    return datetime.now(timezone.utc)


class ArchwayModel(BaseModel):
    """The base class for all Archway data contracts.

    LEARNING NOTE: extra="forbid"
      By default Pydantic silently ignores fields it does not know. For a
      contract that is dangerous: a typo like `licence=` would vanish without
      a trace. "forbid" turns unknown fields into a clear error instead.
    """

    model_config = ConfigDict(extra="forbid")
