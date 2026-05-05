import os
import sys
import unittest
from datetime import datetime, time, timezone


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.schedule_logic import (  # noqa: E402
    apply_schedule_exceptions,
    build_slots,
    merge_time_ranges,
    subtract_time_range,
    validate_exception_fields,
)


class ScheduleLogicTests(unittest.TestCase):
    def test_validate_exception_fields_all_day_requires_null_times(self):
        error = validate_exception_fields("block", True, time(9, 0), time(10, 0))
        self.assertIsNotNone(error)

    def test_validate_exception_fields_timed_requires_start_and_end(self):
        error = validate_exception_fields("open", False, None, time(10, 0))
        self.assertIsNotNone(error)

    def test_validate_exception_fields_timed_requires_start_before_end(self):
        error = validate_exception_fields("open", False, time(12, 0), time(12, 0))
        self.assertIsNotNone(error)

    def test_merge_time_ranges_merges_overlaps(self):
        merged = merge_time_ranges(
            [
                (time(9, 0), time(11, 0)),
                (time(10, 30), time(12, 0)),
                (time(13, 0), time(14, 0)),
            ]
        )
        self.assertEqual(
            merged,
            [(time(9, 0), time(12, 0)), (time(13, 0), time(14, 0))],
        )

    def test_subtract_time_range_splits_interval(self):
        result = subtract_time_range(
            [(time(9, 0), time(18, 0))],
            (time(12, 0), time(13, 0)),
        )
        self.assertEqual(
            result,
            [(time(9, 0), time(12, 0)), (time(13, 0), time(18, 0))],
        )

    def test_apply_schedule_exceptions_all_day_block_wins(self):
        ranges = apply_schedule_exceptions(
            [(time(9, 0), time(18, 0))],
            [{"type": "block", "all_day": True}],
        )
        self.assertEqual(ranges, [])

    def test_apply_schedule_exceptions_open_on_closed_day(self):
        ranges = apply_schedule_exceptions(
            [],
            [
                {
                    "type": "open",
                    "all_day": False,
                    "start_time": time(10, 0),
                    "end_time": time(14, 0),
                }
            ],
        )
        self.assertEqual(ranges, [(time(10, 0), time(14, 0))])

    def test_build_slots_respects_blocked_ranges(self):
        open_ranges = [
            (
                datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 30, 11, 0, tzinfo=timezone.utc),
            )
        ]
        blocked_ranges = [
            (
                datetime(2026, 5, 30, 9, 30, tzinfo=timezone.utc),
                datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc),
            )
        ]

        slots = build_slots(
            open_ranges=open_ranges,
            blocked_ranges=blocked_ranges,
            duration_minutes=30,
            preferred_time="10:00",
            step_minutes=15,
        )

        starts = [slot["start_time"] for slot in slots]
        self.assertIn("9:00 AM", starts)
        self.assertNotIn("9:15 AM", starts)
        self.assertIn("10:00 AM", starts)

        preferred = [slot for slot in slots if slot["start_time"] == "10:00 AM"][0]
        self.assertTrue(preferred["is_preferred"])

    def test_build_slots_buffer_zero_same_as_before(self):
        open_ranges = [
            (
                datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc),
            )
        ]

        old_behavior = build_slots(
            open_ranges=open_ranges,
            blocked_ranges=[],
            duration_minutes=30,
            step_minutes=15,
        )
        explicit_zero = build_slots(
            open_ranges=open_ranges,
            blocked_ranges=[],
            duration_minutes=30,
            buffer_minutes=0,
            step_minutes=15,
        )

        self.assertEqual(explicit_zero, old_behavior)

    def test_build_slots_buffer_keeps_display_end_without_buffer(self):
        open_ranges = [
            (
                datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc),
            )
        ]

        slots = build_slots(
            open_ranges=open_ranges,
            blocked_ranges=[],
            duration_minutes=30,
            buffer_minutes=10,
            step_minutes=15,
        )

        self.assertEqual(slots[0]["start_time"], "9:00 AM")
        self.assertEqual(slots[0]["end_datetime"], "2026-05-30T09:30:00+00:00")
        self.assertNotIn("9:30 AM", [slot["start_time"] for slot in slots])

    def test_build_slots_existing_block_respects_buffer_overlap(self):
        open_ranges = [
            (
                datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 30, 11, 0, tzinfo=timezone.utc),
            )
        ]
        blocked_ranges = [
            (
                datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 30, 9, 40, tzinfo=timezone.utc),
            )
        ]

        slots = build_slots(
            open_ranges=open_ranges,
            blocked_ranges=blocked_ranges,
            duration_minutes=30,
            buffer_minutes=10,
            step_minutes=10,
        )

        starts = [slot["start_time"] for slot in slots]
        self.assertNotIn("9:30 AM", starts)
        self.assertIn("9:40 AM", starts)


if __name__ == "__main__":
    unittest.main()
