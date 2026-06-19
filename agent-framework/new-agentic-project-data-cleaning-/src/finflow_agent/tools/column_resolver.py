"""Column resolver for the FinFlow Agent Service.

Maps an LLM-requested field name (e.g. ``"birthday"``, ``"gender"``,
``"amount"``) to an actual dataframe column with a confidence score in
``[0.0, 1.0]``. The filter agent uses the resolution to gate its filter
conditions behind :data:`CONFIDENCE_THRESHOLD`; below that threshold the
agent consults the ``LOW_CONFIDENCE_POLICY`` (``warn`` | ``fail`` |
``quarantine``) instead of silently applying the wrong column.

This module implements design Component 2 of the agent-pipeline-hardening
spec and corresponds to acceptance criteria 7.1 - 7.9.

Matching tiers (checked in order, deterministic):

1. **Exact case-insensitive match** against ``ColumnProfile.original_name``
   → ``confidence == 1.0``.
2. **Normalized-name match** against ``ColumnProfile.normalized_name``
   → ``confidence == 0.95``.
3. **Known synonym** for the column's ``semantic_guess``
   → ``confidence == 0.85``.
4. **Fuzzy fallback** via ``rapidfuzz.fuzz.token_sort_ratio`` divided by 100
   → ``confidence == fuzzy_score`` (in ``[0.0, 1.0]``).

Determinism: identical inputs MUST produce identical :class:`ColumnResolution`
objects. The scoring loop is order-stable and the synonym table is a
constant ``frozenset`` mapping.
"""

from __future__ import annotations

from typing import List, Mapping, Optional, Tuple

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from finflow_agent.tools.config import (
    LowConfidencePolicy,
    get_low_confidence_policy,
)
from finflow_agent.tools.dataframe_profile import (
    ColumnProfile,
    DataFrameProfile,
    _normalize_name,
)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD: float = 0.75
"""Minimum confidence below which the filter agent must not silently apply
a condition. Matches the default returned by
:func:`finflow_agent.tools.config.get_confidence_threshold`. Exposed as a
module-level constant so design Example 5
(``from finflow_agent.tools.column_resolver import CONFIDENCE_THRESHOLD``)
keeps working without an env-var lookup.
"""


# Per-semantic-guess synonyms. A requested field that matches one of these
# tokens (case-insensitive, optionally after normalization) is treated as a
# confidence ``0.85`` match against any column profile whose
# ``semantic_guess`` equals the dictionary key. Tokens are stored in their
# normalized form so they survive the normalization pass without surprises.
_KNOWN_SYNONYMS: Mapping[str, frozenset[str]] = {
    "date": frozenset(
        {
            "date",
            "datetime",
            "timestamp",
            "time",
            "dob",
            "date_of_birth",
            "birth_date",
            "birthdate",
            "birthday",
            "bday",
            "created",
            "created_at",
            "created_on",
            "updated",
            "updated_at",
            "modified",
            "modified_at",
        }
    ),
    "currency": frozenset(
        {
            "amount",
            "price",
            "cost",
            "fee",
            "total",
            "revenue",
            "salary",
            "income",
            "balance",
            "money",
            "payment",
            "charge",
            "usd",
            "eur",
            "gbp",
        }
    ),
    "numeric": frozenset(
        {
            "count",
            "qty",
            "quantity",
            "number",
            "num",
            "score",
            "rating",
            "rank",
            "age",
            "n",
        }
    ),
    "categorical": frozenset(
        {
            "category",
            "type",
            "kind",
            "group",
            "label",
            "status",
            "class",
            "tier",
            "segment",
        }
    ),
    "boolean": frozenset(
        {
            "flag",
            "active",
            "enabled",
            "is_active",
            "is_enabled",
            "yes_no",
            "bool",
            "boolean",
        }
    ),
    "string": frozenset(
        {
            "name",
            "title",
            "description",
            "label",
            "text",
            "note",
            "comment",
        }
    ),
    "unknown": frozenset(),
}


# ---------------------------------------------------------------------------
# Public Pydantic model
# ---------------------------------------------------------------------------


class ColumnResolution(BaseModel):
    """Outcome of mapping an LLM-requested field name to a dataframe column.

    Attributes
    ----------
    requested_field:
        The original name the LLM (or caller) asked for, preserved verbatim
        so the audit log can show what was requested.
    matched_column:
        The ``original_name`` of the best-matching :class:`ColumnProfile`.
    semantic_type:
        The matched column's ``semantic_guess`` (e.g. ``"date"``,
        ``"currency"``, ``"numeric"``, ``"categorical"``, ``"boolean"``,
        ``"string"``, ``"unknown"``).
    confidence:
        Score in ``[0.0, 1.0]``. ``1.0`` for an exact case-insensitive
        match, ``0.95`` for a normalized-name match, ``0.85`` for a
        semantic-guess synonym match, otherwise the fuzzy
        ``token_sort_ratio`` divided by 100.
    reason:
        Human-readable explanation of which tier produced the match.
    """

    requested_field: str
    matched_column: str
    semantic_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


# ---------------------------------------------------------------------------
# Internal scoring
# ---------------------------------------------------------------------------


def _score_match(
    requested_lower: str,
    requested_normalized: str,
    col: ColumnProfile,
) -> Tuple[float, str]:
    """Return ``(score, reason)`` for matching *col* against the request.

    Tiers are checked in the documented order and the first hit wins. The
    function is deterministic: identical inputs always return identical
    tuples.
    """
    col_original_lower = col.original_name.strip().lower()

    # Tier 1: case-insensitive exact match against the column's original name.
    if requested_lower == col_original_lower:
        return (1.0, "exact name match (case-insensitive)")

    # Tier 2: normalized-name match (only meaningful when the normalized
    # request is non-empty; otherwise an all-symbol request would falsely
    # match every column whose normalized_name is also empty).
    if requested_normalized and requested_normalized == col.normalized_name:
        return (0.95, "normalized name match")

    # Tier 3: known synonym for the column's semantic_guess.
    synonyms = _KNOWN_SYNONYMS.get(str(col.semantic_guess), frozenset())
    if synonyms and (
        requested_lower in synonyms or requested_normalized in synonyms
    ):
        return (0.85, f"semantic synonym match ({col.semantic_guess})")

    # Tier 4: fuzzy token-sort similarity.
    fuzzy_score = (
        fuzz.token_sort_ratio(requested_lower, col_original_lower) / 100.0
    )
    if fuzzy_score >= CONFIDENCE_THRESHOLD:
        return (fuzzy_score, "fuzzy name match")
    return (fuzzy_score, "low-confidence fuzzy match")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_column(
    requested_field: str,
    profile: DataFrameProfile,
) -> ColumnResolution:
    """Resolve *requested_field* against the columns in *profile*.

    Returns a :class:`ColumnResolution` whose ``confidence`` is in
    ``[0.0, 1.0]``. The function is deterministic: identical inputs always
    produce identical output (acceptance criterion 7.5).

    Raises
    ------
    ValueError
        When ``requested_field`` is not a non-empty string, or when
        ``profile.columns`` is empty.
    """
    if not isinstance(requested_field, str) or not requested_field.strip():
        raise ValueError("requested_field must be a non-empty string")
    if not profile.columns:
        raise ValueError("profile must contain at least one column")

    requested_lower = requested_field.strip().lower()
    requested_normalized = _normalize_name(requested_field)

    best_match: Optional[ColumnProfile] = None
    best_score: float = -1.0  # so even a 0.0 fuzzy hit beats the sentinel
    best_reason: str = "no plausible match"

    for col in profile.columns:
        score, reason = _score_match(requested_lower, requested_normalized, col)
        if score > best_score:
            best_match = col
            best_score = score
            best_reason = reason

    # ``best_match`` is guaranteed to be set because ``profile.columns`` is
    # non-empty and every iteration assigns at least once (sentinel is -1.0).
    assert best_match is not None  # for type-checkers
    final_score = max(best_score, 0.0)

    return ColumnResolution(
        requested_field=requested_field,
        matched_column=best_match.original_name,
        semantic_type=str(best_match.semantic_guess),
        confidence=float(final_score),
        reason=best_reason,
    )


def resolve_columns(
    requested_fields: List[str],
    profile: DataFrameProfile,
) -> List[ColumnResolution]:
    """Resolve every entry in *requested_fields* against *profile*.

    Deterministic: the same ``(requested_fields, profile)`` pair always
    produces the same list, in the same order (acceptance criterion 7.5).
    """
    return [resolve_column(field, profile) for field in requested_fields]


# ---------------------------------------------------------------------------
# Low-confidence policy decision surface
# ---------------------------------------------------------------------------


def enforce_low_confidence_policy(
    resolution: ColumnResolution,
    policy: Optional[LowConfidencePolicy] = None,
) -> Tuple[str, Optional[str]]:
    """Return the policy decision for *resolution*.

    The filter agent calls this once per resolved column to decide whether
    to apply, skip, fail, or quarantine the offending condition. The result
    is one of:

    * ``("allow", None)`` — confidence is at or above
      :data:`CONFIDENCE_THRESHOLD`; the condition can be applied.
    * ``("warn", message)`` — policy is ``"warn"`` and confidence is below
      threshold; the caller should append *message* to
      ``AgentResult.warnings`` and skip the condition.
    * ``("fail", message)`` — policy is ``"fail"`` and confidence is below
      threshold; the caller should return
      ``AgentResult(status="failed", error_message=message)``.
    * ``("quarantine", message)`` — policy is ``"quarantine"`` and
      confidence is below threshold; the caller should signal quarantine
      to the orchestrator and not apply the condition.

    When *policy* is ``None`` the function reads the policy from
    :func:`finflow_agent.tools.config.get_low_confidence_policy`, which
    honors the ``LOW_CONFIDENCE_POLICY`` environment variable.

    The message names the requested field, the matched column, and the
    confidence value, satisfying acceptance criterion 7.8.
    """
    if resolution.confidence >= CONFIDENCE_THRESHOLD:
        return ("allow", None)

    effective_policy = policy if policy is not None else get_low_confidence_policy()
    message = (
        f"Low-confidence column match: requested_field="
        f"{resolution.requested_field!r}, matched_column="
        f"{resolution.matched_column!r}, "
        f"confidence={resolution.confidence:.4f} "
        f"(< {CONFIDENCE_THRESHOLD:.2f})."
    )
    return (effective_policy, message)


__all__ = [
    "CONFIDENCE_THRESHOLD",
    "ColumnResolution",
    "resolve_column",
    "resolve_columns",
    "enforce_low_confidence_policy",
]
