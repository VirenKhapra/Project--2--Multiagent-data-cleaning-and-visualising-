"""Visualization intent enricher with field grounding.

Detects chart requests in user prompts, resolves field references against
the dataframe profile's source_columns, and produces grounded VisualizeIntent
actions where each chart has a resolved_column for its category dimension.

Never defaults to a fallback column. If the field cannot be resolved, the
action is marked as needs_clarification.
"""

from __future__ import annotations

import re
from typing import Any

from finflow_agent.planning.trigger_detector import TriggerDetector


_detector = TriggerDetector()


# ---------------------------------------------------------------------------
# Identifier normalization (shared with column resolution)
# ---------------------------------------------------------------------------

def normalize_identifier(value: str) -> str:
    """Normalize a natural-language field reference to a column identifier.

    "Education Level" → "education_level"
    "loan purpose"    → "loan_purpose"
    "annual income"   → "annual_income"
    """
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


# ---------------------------------------------------------------------------
# Chart request parsing
# ---------------------------------------------------------------------------

_CHART_TYPE_PATTERN = re.compile(
    r"\b(?:generate|create|show|display|make|build|produce)?\s*(?:a\s+|the\s+)?"
    r"(?P<type>pie|pi|bar|line|scatter|histogram|grouped\s+bar|stacked\s+bar)\s*"
    r"(?:chart|graph|plot|visualization|diagram)s?\s*"
    r"(?:showing|displaying|of|for|that|comparing|with|having)?\s*"
    r"(?:the\s+)?(?:overall\s+)?(?:different\s+)?(?:fields\s+of\s+)?(?:reasons?\s+(?:of|for)\s+)?"
    r"(?P<desc>[^.;]+?)(?=[.;]|$)",
    re.IGNORECASE,
)


def _parse_chart_requests(prompt: str) -> list[dict[str, Any]]:
    """Parse multiple chart requests from a prompt, splitting on connectors."""
    charts: list[dict[str, Any]] = []
    seen_descriptions: set[str] = set()

    # Pre-check: "bar graph and pie chart for X" pattern (shared field)
    shared_field_match = re.search(
        r"\b(?P<type1>pie|pi|bar|line|scatter)\s*(?:chart|graph)\s+"
        r"and\s+(?P<type2>pie|pi|bar|line|scatter)\s*(?:chart|graph)\s+"
        r"(?:for|of|showing|displaying)\s+(?P<desc>.+?)(?=[.;]|$)",
        prompt, re.IGNORECASE,
    )
    if not shared_field_match:
        shared_field_match = re.search(
            r"\b(?:generate|create|show|make)\s+(?:the\s+|a\s+)?"
            r"(?P<type1>pie|pi|bar|line|scatter)\s*(?:chart|graph)\s+"
            r"and\s+(?P<type2>pie|pi|bar|line|scatter)\s*(?:chart|graph)\s+"
            r"(?:for|of|showing|displaying)\s+(?P<desc>.+?)(?=[.;]|$)",
            prompt, re.IGNORECASE,
        )
    if shared_field_match:
        type1 = shared_field_match.group("type1").lower()
        type2 = shared_field_match.group("type2").lower()
        desc = shared_field_match.group("desc").strip()
        type1 = "pie" if type1 == "pi" else type1
        type2 = "pie" if type2 == "pi" else type2
        return [
            {"kind": "visualize", "chart_type": type1, "description": desc, "fields": []},
            {"kind": "visualize", "chart_type": type2, "description": desc, "fields": []},
        ]

    segments = re.split(
        r"\band\s+also\b|\balso\s+generate\b|\balso\s+create\b|\balso\s+show\b"
        r"|\band\s+(?:the\s+)?(?=(?:pie|pi|bar|line|scatter|histogram)\s*(?:chart|graph))"
        r"|\.\s*(?:Next|Then|Also|Finally|Additionally)\s*,?\s*"
        r"|\.\s+",
        prompt,
        flags=re.IGNORECASE,
    )

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        match = _CHART_TYPE_PATTERN.search(segment)
        if not match:
            continue

        chart_type_raw = match.group("type").strip().lower()
        description = match.group("desc").strip()

        if "grouped" in chart_type_raw or "stacked" in chart_type_raw:
            chart_type = "bar"
        elif chart_type_raw in ("pi", "pie"):
            chart_type = "pie"
        else:
            chart_type = chart_type_raw

        desc_key = description.lower()[:50]
        if desc_key in seen_descriptions:
            continue
        seen_descriptions.add(desc_key)

        charts.append({
            "kind": "visualize",
            "chart_type": chart_type,
            "description": description,
            "fields": [],
        })

    return charts


# ---------------------------------------------------------------------------
# Field grounding against source_columns
# ---------------------------------------------------------------------------

def _resolve_visualization_field(
    description: str,
    source_columns: list[str],
) -> dict[str, Any] | None:
    """Resolve a visualization field description to an actual column.

    Uses normalized identifier matching — no fallback to gender or any
    other arbitrary column.

    Returns a grounded field dict or None if unresolvable.
    """
    if not description or not source_columns:
        return None

    # Build normalized lookup
    col_normalized_map: dict[str, str] = {}
    for col in source_columns:
        col_normalized_map[normalize_identifier(col)] = col

    # Normalize the description
    desc_normalized = normalize_identifier(description)

    # Exact normalized match
    if desc_normalized in col_normalized_map:
        return {
            "role": "category",
            "raw_reference": description,
            "resolved_column": col_normalized_map[desc_normalized],
            "resolution_method": "exact_normalized_match",
            "confidence": 1.0,
        }

    # Substring match: description contains a column name or vice versa
    for col_norm, col_real in col_normalized_map.items():
        if col_norm in desc_normalized or desc_normalized in col_norm:
            return {
                "role": "category",
                "raw_reference": description,
                "resolved_column": col_real,
                "resolution_method": "substring_match",
                "confidence": 0.9,
            }

    # Word overlap: any significant word from description matches column parts
    desc_parts = [p for p in desc_normalized.split("_") if len(p) > 2]
    for col_norm, col_real in col_normalized_map.items():
        col_parts = col_norm.split("_")
        if any(dp in col_parts for dp in desc_parts):
            return {
                "role": "category",
                "raw_reference": description,
                "resolved_column": col_real,
                "resolution_method": "word_overlap_match",
                "confidence": 0.8,
            }

    return None


# ---------------------------------------------------------------------------
# Main enrichment function
# ---------------------------------------------------------------------------

def enrich_intent_with_visualization(
    canonical_intent: dict[str, Any],
) -> dict[str, Any]:
    """Enrich canonical intent with grounded VisualizeIntent actions.

    Each chart's category field is resolved against source_columns from
    the dataframe profile. If resolution fails, the field is left unresolved
    (no fallback to gender or any default column).
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

    # Get source columns for grounding
    profile = canonical_intent.get("dataframe_profile", {})
    source_columns = []
    if isinstance(profile, dict):
        src = profile.get("source_columns") or profile.get("columns")
        if isinstance(src, list):
            if src and isinstance(src[0], str):
                source_columns = src
            elif src and isinstance(src[0], dict):
                source_columns = [c.get("name", "") for c in src if isinstance(c, dict)]

    # Check existing visualize actions
    existing_viz_count = sum(1 for a in actions if isinstance(a, dict) and a.get("kind") == "visualize")

    # Parse chart requests
    chart_requests = _parse_chart_requests(prompt)

    if not chart_requests:
        # Fallback: single-chart detection
        result = _detector.detect(prompt)
        if result.triggered:
            chart_requests = [{
                "kind": "visualize",
                "chart_type": result.chart_type_hint or "bar",
                "description": prompt.split("chart")[-1].strip() if "chart" in prompt.lower() else "",
                "fields": [],
            }]

    if not chart_requests:
        return canonical_intent

    # If we detect more/equal charts than exist, replace
    if existing_viz_count > 0 and len(chart_requests) >= existing_viz_count:
        actions[:] = [a for a in actions if not (isinstance(a, dict) and a.get("kind") == "visualize")]

    # Ground each chart's field and append
    for chart in chart_requests:
        description = chart.get("description", "")
        grounded_field = _resolve_visualization_field(description, source_columns)

        if grounded_field:
            chart["fields"] = [grounded_field]
        # If not grounded, fields stays empty — the viz agent will use
        # description-based matching against the runtime dataframe

        actions.append(chart)

    return canonical_intent


def should_produce_visualization(prompt: str) -> bool:
    """Check whether a prompt should produce a visualization intent."""
    if not prompt or not isinstance(prompt, str):
        return False
    if _parse_chart_requests(prompt):
        return True
    result = _detector.detect(prompt)
    return result.triggered


__all__ = [
    "enrich_intent_with_visualization",
    "normalize_identifier",
    "should_produce_visualization",
]
