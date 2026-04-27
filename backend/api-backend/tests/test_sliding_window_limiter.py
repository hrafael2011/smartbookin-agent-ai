import time

from app.core.sliding_window_limiter import SlidingWindowLimiter


def test_limiter_allows_within_cap():
    lim = SlidingWindowLimiter(max_events=3, window_seconds=10)
    assert lim.is_allowed("a") is True
    assert lim.is_allowed("a") is True
    assert lim.is_allowed("a") is True
    assert lim.is_allowed("a") is False


def test_limiter_resets_after_window():
    lim = SlidingWindowLimiter(max_events=2, window_seconds=1)
    assert lim.is_allowed("k") is True
    assert lim.is_allowed("k") is True
    assert lim.is_allowed("k") is False
    time.sleep(1.05)
    assert lim.is_allowed("k") is True
