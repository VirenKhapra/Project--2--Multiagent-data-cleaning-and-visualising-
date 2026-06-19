from app.services.retry_policy import compute_retry_delay_seconds


def test_retry_delay_grows_with_attempt_number():
    assert compute_retry_delay_seconds(attempt=1, base_delay_seconds=10, max_delay_seconds=35) == 10
    assert compute_retry_delay_seconds(attempt=2, base_delay_seconds=10, max_delay_seconds=35) == 20
    assert compute_retry_delay_seconds(attempt=3, base_delay_seconds=10, max_delay_seconds=35) == 35
