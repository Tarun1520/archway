"""
Structured local logging.

What this file does
    Makes every log line one JSON object, for example:
      {"time": "...", "level": "INFO", "logger": "archway.api",
       "message": "project created", "project_id": "ab12..."}

LEARNING NOTE: why "structured" logs?
    A plain sentence ("created project ab12 for run 9") is easy for a person
    but hard to search. Key-value pairs can be filtered: "show every line
    where run_id = 9". Logs stay on this machine; nothing is sent anywhere.

Two safety rules
    1. Never log secrets or private content (IMPLEMENTATION_GUIDE.md 0.2).
    2. As a second line of defence, any known secret value that still ends up
       in a log line is replaced with "[redacted]" before it is written.

How it plugs in
    app/main.py calls `configure_logging` once at start-up. Other files do:
        logger = logging.getLogger("archway.something")
        logger.info("what happened", extra={"fields": {"run_id": run_id}})
"""

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Turns a log record into one line of JSON."""

    def __init__(self, secrets: list[str] | None = None):
        super().__init__()
        # Only keep real, non-empty secret values. Short values are skipped so
        # we never redact ordinary words by accident.
        self._secrets = [secret for secret in (secrets or []) if secret and len(secret) >= 8]

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Extra key-value pairs passed as  extra={"fields": {...}}
        extra_fields = getattr(record, "fields", None)
        if isinstance(extra_fields, dict):
            entry.update(extra_fields)
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)

        # default=str turns anything JSON cannot handle (dates, paths) into text.
        line = json.dumps(entry, default=str)
        for secret in self._secrets:
            line = line.replace(secret, "[redacted]")
        return line


def configure_logging(level: str = "INFO", secrets: list[str] | None = None) -> None:
    """Send all "archway.*" logs to the terminal as JSON lines."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(secrets))

    archway_logger = logging.getLogger("archway")
    archway_logger.handlers.clear()  # calling this twice must not print lines twice
    archway_logger.addHandler(handler)
    archway_logger.setLevel(level)
    archway_logger.propagate = False  # do not also pass lines to the root logger
