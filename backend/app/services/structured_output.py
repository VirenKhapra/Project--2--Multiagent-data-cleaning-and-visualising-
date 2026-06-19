from __future__ import annotations

from typing import Any


def sanitize_structured_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    return {
        str(key): value
        for key, value in row.items()
        if not str(key).startswith("_")
    }


def sanitize_structured_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [
        sanitized
        for row in rows
        for sanitized in [sanitize_structured_row(row)]
        if sanitized
    ]
