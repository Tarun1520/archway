"""
What any email sender must offer.

LEARNING NOTE: the same plug-in shape as the model and voice providers
    The rest of the app only knows `Mailer.send(...)`. Brevo is one implementation (brevo.py); tests use a fake that
    just remembers what it was asked to send. Changing provider means writing one new file and changing factory.py.
"""

from typing import Protocol


class MailError(Exception):
    """The email could not be sent (the message is safe to log: it never contains the key)."""


class Mailer(Protocol):
    async def send(self, *, to: str, subject: str, text: str, html: str) -> None: ...
