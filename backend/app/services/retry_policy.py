from __future__ import annotations


def compute_retry_delay_seconds(*, attempt: int, base_delay_seconds: int, max_delay_seconds: int) -> int:
    base = max(1, base_delay_seconds)
    cap = max(base, max_delay_seconds)
    delay = base * (2 ** max(0, attempt - 1))
    return min(delay, cap)
