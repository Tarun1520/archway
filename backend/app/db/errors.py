"""Errors raised by the repositories."""


class NotFound(LookupError):
    """Raised when a record with the given id does not exist.

    The API layer turns this into an HTTP 404 response (see app/main.py).
    """

    def __init__(self, kind: str, record_id: str):
        self.kind = kind
        self.record_id = record_id
        super().__init__(f"{kind} '{record_id}' was not found")
