from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Iterable, Optional, Sequence


TimeRange = tuple[time, time]
DateTimeRange = tuple[datetime, datetime]

TIME_STEP_MINUTES = 15


def ranges_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    return start_a < end_b and start_b < end_a


def datetime_ranges_overlap(
    start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime
) -> bool:
    return start_a < end_b and start_b < end_a


def merge_time_ranges(ranges: Iterable[TimeRange]) -> list[TimeRange]:
    normalized = sorted((start, end) for start, end in ranges if start < end)
    if not normalized:
        return []

    merged: list[TimeRange] = [normalized[0]]
    for start, end in normalized[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            if end > last_end:
                merged[-1] = (last_start, end)
        else:
            merged.append((start, end))
    return merged


def subtract_time_range(base_ranges: Sequence[TimeRange], blocked: TimeRange) -> list[TimeRange]:
    block_start, block_end = blocked
    if block_start >= block_end:
        return list(base_ranges)

    result: list[TimeRange] = []
    for start, end in base_ranges:
        if not ranges_overlap(start, end, block_start, block_end):
            result.append((start, end))
            continue

        if start < block_start:
            result.append((start, min(block_start, end)))
        if block_end < end:
            result.append((max(block_end, start), end))

    return merge_time_ranges(result)


def validate_exception_fields(
    exception_type: str,
    all_day: bool,
    start_time: Optional[time],
    end_time: Optional[time],
) -> Optional[str]:
    if exception_type not in {"block", "open"}:
        return "type must be either 'block' or 'open'"

    if all_day:
        if start_time is not None or end_time is not None:
            return "start_time and end_time must be null when all_day is true"
        return None

    if start_time is None or end_time is None:
        return "start_time and end_time are required when all_day is false"

    if start_time >= end_time:
        return "start_time must be earlier than end_time"

    return None


def apply_schedule_exceptions(
    base_ranges: Sequence[TimeRange], exceptions: Sequence[dict]
) -> list[TimeRange]:
    # Highest-priority hard close for the date.
    if any(exc.get("type") == "block" and exc.get("all_day") for exc in exceptions):
        return []

    ranges = merge_time_ranges(base_ranges)

    # All-day open overrides weekly baseline.
    if any(exc.get("type") == "open" and exc.get("all_day") for exc in exceptions):
        ranges = [(time(0, 0), time(23, 59))]

    timed_opens: list[TimeRange] = []
    timed_blocks: list[TimeRange] = []
    for exc in exceptions:
        if exc.get("all_day"):
            continue
        start = exc.get("start_time")
        end = exc.get("end_time")
        if not isinstance(start, time) or not isinstance(end, time):
            continue
        if start >= end:
            continue
        if exc.get("type") == "open":
            timed_opens.append((start, end))
        elif exc.get("type") == "block":
            timed_blocks.append((start, end))

    if timed_opens:
        ranges = merge_time_ranges([*ranges, *timed_opens])
    for blocked in timed_blocks:
        ranges = subtract_time_range(ranges, blocked)

    return ranges


def _extract_hour_candidates(preferred_time: Optional[str]) -> set[int]:
    if not preferred_time:
        return set()

    text = preferred_time.strip().lower()
    candidates: set[int] = set()

    if "mañana" in text:
        return set(range(8, 12))
    if "tarde" in text:
        return set(range(12, 18))
    if "noche" in text:
        return set(range(18, 23))

    for fmt in ("%H:%M", "%H", "%I:%M %p", "%I %p"):
        try:
            parsed = datetime.strptime(text.upper(), fmt)
            candidates.add(parsed.hour)
            return candidates
        except ValueError:
            continue

    return candidates


def build_slots(
    open_ranges: Sequence[DateTimeRange],
    blocked_ranges: Sequence[DateTimeRange],
    duration_minutes: int,
    buffer_minutes: int = 0,
    preferred_time: Optional[str] = None,
    step_minutes: int = TIME_STEP_MINUTES,
) -> list[dict]:
    if duration_minutes <= 0:
        return []

    preferred_hours = _extract_hour_candidates(preferred_time)
    duration_delta = timedelta(minutes=duration_minutes)
    slot_block_delta = timedelta(minutes=duration_minutes + max(0, int(buffer_minutes or 0)))
    step_delta = timedelta(minutes=step_minutes)

    slots: list[dict] = []
    for range_start, range_end in open_ranges:
        cursor = range_start
        while cursor + slot_block_delta <= range_end:
            display_end_cursor = cursor + duration_delta
            block_end_cursor = cursor + slot_block_delta

            is_conflicting = any(
                datetime_ranges_overlap(cursor, block_end_cursor, blocked_start, blocked_end)
                for blocked_start, blocked_end in blocked_ranges
            )
            if not is_conflicting:
                slots.append(
                    {
                        "start_time": cursor.strftime("%I:%M %p").lstrip("0"),
                        "start_datetime": cursor.isoformat(),
                        "end_datetime": display_end_cursor.isoformat(),
                        "is_preferred": cursor.hour in preferred_hours if preferred_hours else False,
                    }
                )

            cursor += step_delta

    return slots
