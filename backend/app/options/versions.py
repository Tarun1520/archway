"""
Which option versions count.

    A revision never edits an option: it saves the NEXT version of it. So a run holds every version
    ever drafted, and these helpers answer "which one is current?" and "which ones may be shown?".

Plain dicts in and out (the workflow state holds plain data), validated into ArchitectureOption only
where a shape is needed.
"""

from typing import Any


def latest(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The newest version of each option, in the order the options first appeared."""
    newest: dict[str, dict[str, Any]] = {}
    for item in options:
        if item["id"] not in newest or item["version"] > newest[item["id"]]["version"]:
            newest[item["id"]] = item
    return list(newest.values())


def presented(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each option, its newest version that passed the review gate: the only ones the person is shown.

    A revision that fails review is therefore never shown in place of the version that was fine: the earlier
    passing version stays current, and the failure is reported in the notes.
    """
    shown: dict[str, dict[str, Any]] = {}
    for item in options:
        if (item.get("review") or {}).get("passed") is True and (item["id"] not in shown or item["version"] > shown[item["id"]]["version"]):
            shown[item["id"]] = item
    return list(shown.values())


def unreviewed(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Versions drafted but not yet through the review gate."""
    return [o for o in options if o.get("review") is None]


def find(options: list[dict[str, Any]], option_id: str, version: int | None = None) -> dict[str, Any] | None:
    matches = [o for o in options if o["id"] == option_id and (version is None or o["version"] == version)]
    return max(matches, key=lambda o: o["version"]) if matches else None


def next_option_number(options: list[dict[str, Any]]) -> int:
    numbers = [int(o["id"].removeprefix("OPT-")) for o in options if o["id"].startswith("OPT-") and o["id"][4:].isdigit()]
    return max(numbers, default=0) + 1
