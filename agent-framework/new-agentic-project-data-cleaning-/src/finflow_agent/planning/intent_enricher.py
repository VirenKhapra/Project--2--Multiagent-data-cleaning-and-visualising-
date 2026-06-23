"""Visualization intent enricher for the canonical intent pipeline.

Integrates the TriggerDetector with the intent classification pipeline.
When trigger language is detected in the user prompt, this module enriches
the canonical intent's actions list with VisualizeIntent actions — one per
detected chart request.

Supports multi-chart prompts: "show a pie chart of X, a bar chart of Y,
and a line chart of Z" produces 3 separate VisualizeIntent actions.

Flow:
    User Prompt → parse_chart_requests() → N chart specs detected?
        YES → Add N VisualizeIntent actions to canonical intent
        NO  → Leave canonical intent unchanged

Requirements: 1.1, 1.4, 2.1, 5.2, 13.1, 13.2
"""

from __future__ import annotations

import re
from typing import Any

from finflow_agent.planning.trigger_detector import TriggerDetector


# Module-level singleton detector instance.
_detector = TriggerDetector()

# Chart type patterns for multi-chart extraction
_CHART_TYPE_PATTERN = re.compile(
    r"\b(?:generate|create|show|display|make)\s+(?:a\s+)?(?P<type>pie|bar|line|scatter|histogram|grouped\s+bar|stacked\s+bar)\s*"
    r"(?:chart|graph|plot|visualization)s?\s*"
    r"(?:showing|displaying|of|for|that|comparing|with)?\s*"
    r"(?:the\s+)?(?:overall\s+)?(?P<desc>[^.;]+?)(?=[.;]|$)",
    re.IGNORECASE,
)

_CHART_SEPARATOR = re.compile(
    r"\.\s*(?:next|then|also|finally|additionally)?\s*,?\s*"
    r"|\bnext\b\s*,?\s*"
    r"|\bfinally\b\s*,?\s*"
    r"|\balso\b\s*,?\s*"
    r"|\bthen\b\s*,?\s*",
    re.IGNORECASE,
)


def _parse_chart_requests(prompt: str) -> list[dict[str, Any]]:
    """Parse multiple chart requests from a prompt.

    Detects patterns like:
    - "pie chart showing X"
    - "bar chart comparing Y"
    - "grouped bar chart that displays Z"

    Returns a list of chart spec dicts, one per detected chart.
    """
    charts: list[dict[str, Any]] = []
    seen_descriptions: set[str] = set()

    for match in _CHART_TYPE_PATTERN.finditer(prompt):
        chart_type_raw = match.group("type").strip().lower()
        description = match.group("desc").strip()

        # Normalize chart type
        if "grouped" in chart_type_raw or "stacked" in chart_type_raw:
            chart_type = "bar"
        else:
            chart_type = chart_type_raw

        # Deduplicate by description
        desc_key = description.lower()[:50]
        if desc_key in seen_descriptions:
            continue
        seen_descriptions.add(desc_key)

        charts.append({
            "kind": "visualize",
            "chart_type": chart_type,
            "fields": [],
            "description": description,
        })

    return charts


def enrich_intent_with_visualization(
    canonical_intent: dict[str, Any],
) -> dict[str, Any]:
    """Enrich a canonical intent dict with VisualizeIntent actions for each detected chart.

    Supports multi-chart prompts by parsing individual chart requests.
    Falls back to single-chart detection via TriggerDetector for simpler prompts.

    Args:
        canonical_intent: A canonical intent dictionary.

    Returns:
        The same dict with VisualizeIntent actions appended.

    Requirements: 1.1, 1.4, 2.1, 5.2, 13.1, 13.2
    """
    if not isinstance(canonical_intent, dict):
        return canonical_intent

    prompt = canonical_intent.get("original_prompt", "")
    if not prompt or not isinstance(prompt, str):
        return canonical_intent

    actions = canonical_intent.get("actions", [])
    if not isinstance(actions, list):
        actions = []
        canonical_intent["actions"] = actions

    # Skip if visualize actions already exist
    if any(isinstance(a, dict) and a.get("kind") == "visualize" for a in actions):
        return canonical_intent

    # Try multi-chart parsing first
    chart_requests = _parse_chart_requests(prompt)

    if chart_requests:
        for chart in chart_requests:
            actions.append(chart)
        return canonical_intent

    # Fallback: single-chart detection via TriggerDetector
    result = _detector.detect(prompt)
    if not result.triggered:
        return canonical_intent

    actions.append({
        "kind": "visualize",
        "chart_type": result.chart_type_hint,
        "fields": [],
    })

    return canonical_intent


def should_produce_visualization(prompt: str) -> bool:
    """Check whether a prompt should produce a visualization intent."""
    if not prompt or not isinstance(prompt, str):
        return False
    # Check multi-chart
    if _parse_chart_requests(prompt):
        return True
    # Fallback single-chart
    result = _detector.detect(prompt)
    return result.triggered


__all__ = [
    "enrich_intent_with_visualization",
    "should_produce_visualization",
]
