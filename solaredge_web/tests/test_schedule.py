# Copyright (c) 2026 8ecker.de
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from app.config import Config
from app.schedule import next_poll_at, wait_for_poll


BERLIN = ZoneInfo('Europe/Berlin')


class PollScheduleTests(unittest.TestCase):
    def slot(self, value, interval=900):
        return next_poll_at(datetime.fromisoformat(value), interval, 'Europe/Berlin')

    def test_default_four_fixed_slots_per_hour(self):
        self.assertEqual(Config().poll_interval, 900)
        instant = datetime(2026, 10, 3, 12, 0, tzinfo=BERLIN)
        slots = []
        for _ in range(4):
            instant = next_poll_at(instant, 900, 'Europe/Berlin')
            slots.append(instant.astimezone(BERLIN).strftime('%H:%M:%S'))
        self.assertEqual(slots, ['12:00:01', '12:15:01', '12:30:01', '12:45:01'])

    def test_midnight_is_one_second_after_new_local_day(self):
        for interval in (30, 37, 900, 1800, 3600):
            with self.subTest(interval=interval):
                slot = self.slot('2026-10-03T23:59:59+02:00', interval)
                self.assertEqual(slot.astimezone(BERLIN).isoformat(), '2026-10-04T00:00:01+02:00')

    def test_boundary_is_strictly_future_and_does_not_duplicate(self):
        before = self.slot('2026-10-03T12:15:00.999999+02:00')
        exact = self.slot('2026-10-03T12:15:01+02:00')
        self.assertEqual(before.astimezone(BERLIN).strftime('%H:%M:%S'), '12:15:01')
        self.assertEqual(exact.astimezone(BERLIN).strftime('%H:%M:%S'), '12:30:01')

    def test_completion_time_does_not_shift_slots_or_replay_missed_cycles(self):
        self.assertEqual(self.slot('2026-10-03T12:00:23+02:00'), self.slot('2026-10-03T12:14:59+02:00'))
        late = self.slot('2026-10-03T12:39:20+02:00')
        self.assertEqual(late.astimezone(BERLIN).strftime('%H:%M:%S'), '12:45:01')

    def test_spring_change_skips_nonexistent_hour(self):
        before = datetime.fromisoformat('2026-03-29T01:45:01+01:00')
        slot = next_poll_at(before, 900, 'Europe/Berlin')
        self.assertEqual(slot.astimezone(BERLIN).isoformat(), '2026-03-29T03:00:01+02:00')
        self.assertEqual(slot - before, timedelta(minutes=15))

    def test_autumn_change_runs_both_repeated_hours_in_real_time_order(self):
        before = datetime.fromisoformat('2026-10-25T02:45:01+02:00')
        slot = next_poll_at(before, 900, 'Europe/Berlin')
        self.assertEqual(slot.astimezone(BERLIN).isoformat(), '2026-10-25T02:00:01+01:00')
        self.assertEqual(slot - before, timedelta(minutes=15))
        for _ in range(3):
            slot = next_poll_at(slot, 900, 'Europe/Berlin')
        self.assertEqual(slot.astimezone(BERLIN).isoformat(), '2026-10-25T02:45:01+01:00')
        self.assertEqual(next_poll_at(slot, 900, 'Europe/Berlin').astimezone(BERLIN).hour, 3)

    def test_custom_interval_anchors_to_local_midnight_in_fractional_timezone(self):
        slot = next_poll_at(datetime.fromisoformat('2026-10-03T12:06:41+05:45'), 1000, 'Asia/Kathmandu')
        self.assertEqual(slot.astimezone(ZoneInfo('Asia/Kathmandu')).isoformat(), '2026-10-03T12:13:21+05:45')

    def test_rejects_naive_clock_and_out_of_range_interval(self):
        with self.assertRaises(ValueError):
            next_poll_at(datetime(2026, 10, 3), 900, 'Europe/Berlin')
        for interval in (29, 3601, True):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                next_poll_at(datetime.now(timezone.utc), interval, 'Europe/Berlin')


class PollWaitTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_interrupts_wait_immediately(self):
        stop, health = asyncio.Event(), Mock()
        current = datetime(2026, 10, 3, 12, 2, tzinfo=timezone.utc)
        task = asyncio.create_task(wait_for_poll(stop, 900, 'Europe/Berlin', health, clock=lambda: current))
        await asyncio.sleep(0)
        stop.set()
        await asyncio.wait_for(task, 0.5)
        self.assertTrue(health.update.called)

    async def test_wall_clock_forward_jump_ends_wait_without_long_monotonic_delay(self):
        stop, health = asyncio.Event(), Mock()
        readings = iter([datetime.fromisoformat(value) for value in (
            '2026-10-03T12:00:02+00:00', '2026-10-03T12:00:02+00:00', '2026-10-03T13:00:02+00:00',
        )])
        waits = []

        async def timeout(awaitable, *, timeout):
            awaitable.close()
            waits.append(timeout)
            raise asyncio.TimeoutError

        with patch('app.schedule.asyncio.wait_for', side_effect=timeout):
            await wait_for_poll(stop, 900, 'Europe/Berlin', health, clock=lambda: next(readings))
        self.assertEqual(waits, [10])

    async def test_backward_clock_jump_recalculates_next_wall_clock_slot(self):
        stop, health = asyncio.Event(), Mock()
        readings = iter([datetime.fromisoformat(value) for value in (
            '2026-10-03T12:40:00+00:00', '2026-10-03T12:10:00+00:00', '2026-10-03T12:15:01+00:00',
        )])

        async def timeout(awaitable, *, timeout):
            awaitable.close()
            raise asyncio.TimeoutError

        with patch('app.schedule.asyncio.wait_for', side_effect=timeout):
            await wait_for_poll(stop, 900, 'Europe/Berlin', health, clock=lambda: next(readings))
        targets = [call.kwargs['next_poll_at'] for call in health.update.call_args_list if 'next_poll_at' in call.kwargs]
        self.assertEqual(targets, ['2026-10-03T12:45:01+00:00', '2026-10-03T12:15:01+00:00'])


if __name__ == '__main__':
    unittest.main()
