"""LLM call telemetry — structured logging for every Groq API interaction."""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("llm_telemetry")
# Ensure the telemetry logger outputs to stderr (captured by Docker)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(name)s | %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.DEBUG)


def _safe_key_fingerprint(api_key: str) -> str:
    """Return last 4 chars of API key for safe logging."""
    if not api_key or len(api_key) < 8:
        return "NONE"
    return f"...{api_key[-4:]}"


def _prompt_hash(messages: list) -> str:
    """SHA-256 hash of rendered messages for deduplication detection."""
    content = json.dumps(messages, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _prompt_stats(messages: list) -> dict:
    """Safe prompt measurements without logging content."""
    system_chars = sum(len(m.get("content", "") or "") for m in messages if m.get("role") == "system")
    user_chars = sum(len(m.get("content", "") or "") for m in messages if m.get("role") == "user")
    return {
        "system_prompt_characters": system_chars,
        "user_prompt_characters": user_chars,
        "message_count": len(messages),
    }


def log_llm_started(
    *,
    service: str,
    operation: str,
    caller_file: str,
    caller_function: str,
    model: str,
    api_key_source: str,
    api_key: str,
    attempt: int,
    trigger: str,
    messages: list,
    submission_id: str = "",
    job_id: str = "",
    correlation_id: str = "",
    endpoint_or_worker: str = "",
) -> dict:
    """Log llm_call_started and return context dict for completion/failure logging."""
    logical_call_id = str(uuid.uuid4())[:8]
    physical_attempt_id = str(uuid.uuid4())[:8]

    entry = {
        "event": "llm_call_started",
        "logical_call_id": logical_call_id,
        "physical_attempt_id": physical_attempt_id,
        "job_id": job_id,
        "submission_id": submission_id,
        "correlation_id": correlation_id,
        "service": service,
        "endpoint_or_worker": endpoint_or_worker,
        "operation": operation,
        "caller_file": caller_file,
        "caller_function": caller_function,
        "model": model,
        "api_key_source": api_key_source,
        "api_key_fingerprint": _safe_key_fingerprint(api_key),
        "attempt": attempt,
        "trigger": trigger,
        "prompt_hash": _prompt_hash(messages),
        **_prompt_stats(messages),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(json.dumps(entry))
    return {
        "logical_call_id": logical_call_id,
        "physical_attempt_id": physical_attempt_id,
        "start_time": time.perf_counter(),
        **entry,
    }


def log_llm_completed(
    ctx: dict,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    finish_reason: str = "",
) -> None:
    """Log llm_call_completed with actual token usage from provider."""
    duration_ms = (time.perf_counter() - ctx["start_time"]) * 1000
    entry = {
        "event": "llm_call_completed",
        "logical_call_id": ctx["logical_call_id"],
        "physical_attempt_id": ctx["physical_attempt_id"],
        "job_id": ctx.get("job_id", ""),
        "submission_id": ctx.get("submission_id", ""),
        "service": ctx["service"],
        "operation": ctx["operation"],
        "model": ctx["model"],
        "attempt": ctx["attempt"],
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "duration_ms": round(duration_ms, 1),
        "finish_reason": finish_reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(json.dumps(entry))


def log_llm_failed(
    ctx: dict,
    *,
    status_code: int = 0,
    error_type: str = "",
    error_message: str = "",
    headers: dict | None = None,
) -> None:
    """Log llm_call_failed with rate-limit headers when available."""
    duration_ms = (time.perf_counter() - ctx["start_time"]) * 1000
    hdrs = headers or {}
    entry = {
        "event": "llm_call_failed",
        "logical_call_id": ctx["logical_call_id"],
        "physical_attempt_id": ctx["physical_attempt_id"],
        "job_id": ctx.get("job_id", ""),
        "submission_id": ctx.get("submission_id", ""),
        "service": ctx["service"],
        "operation": ctx["operation"],
        "model": ctx["model"],
        "attempt": ctx["attempt"],
        "status_code": status_code,
        "error_type": error_type,
        "error_message": error_message[:300],
        "retry_after": hdrs.get("retry-after", ""),
        "rate_limit_limit_tokens": hdrs.get("x-ratelimit-limit-tokens", ""),
        "rate_limit_remaining_tokens": hdrs.get("x-ratelimit-remaining-tokens", ""),
        "rate_limit_reset_tokens": hdrs.get("x-ratelimit-reset-tokens", ""),
        "duration_ms": round(duration_ms, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(json.dumps(entry))


def log_polling_decision(
    *,
    submission_id: str,
    endpoint: str,
    schema_proposal_present: bool,
    summary_present: bool,
    canonical_intent_present: bool,
    fallback_reason: str = "",
    will_rebuild: bool = False,
    will_call_llm: bool = False,
) -> None:
    """Log the decision made inside get_schema_proposal_with_fallback."""
    entry = {
        "event": "polling_decision",
        "submission_id": submission_id,
        "endpoint": endpoint,
        "schema_proposal_present": schema_proposal_present,
        "summary_present": summary_present,
        "canonical_intent_present": canonical_intent_present,
        "fallback_reason": fallback_reason,
        "will_rebuild": will_rebuild,
        "will_call_llm": will_call_llm,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(json.dumps(entry))
