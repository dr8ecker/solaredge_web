# Copyright (c) 2026 8ecker.de
"""Local wall-clock polling slots, including midnight and daylight-saving changes."""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


LOGGER = logging.getLogger(__name__)


def next_poll_at(now: datetime, interval: int, timezone_name: str) -> datetime:
    """Return the first strictly future slot as a UTC datetime.

    Slots are local midnight + 1 second + n * interval, reset every local day.
    Resolve both folds and reject nonexistent local times instead of adding a
    duration to an aware local datetime: that would skip the repeated DST hour.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Polling clock must be timezone-aware')
    if type(interval) is not int or not 30 <= interval <= 3600:
        raise ValueError('Polling interval must be between 30 and 3600 seconds')
    zone = ZoneInfo(timezone_name)
    now = now.astimezone(timezone.utc)
    today = now.astimezone(zone).date()
    earliest = None
    # Three dates also cover a timezone transition that skips a whole date.
    for day_offset in range(3):
        midnight = datetime.combine(today + timedelta(days=day_offset), time())
        for seconds in range(1, 86400, interval):
            local_slot = midnight + timedelta(seconds=seconds)
            for fold in (0, 1):
                candidate = local_slot.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
                if candidate <= now or (earliest is not None and candidate >= earliest):
                    continue
                if candidate.astimezone(zone).replace(tzinfo=None) == local_slot:
                    earliest = candidate
    if earliest is None:
        raise ValueError('Cannot determine next local polling slot')
    return earliest


async def wait_for_poll(stop, interval, timezone_name, health, *, clock=None):
    """Wait for one slot, checking wall time and cancellation at least every 10 s.

    Computing a new slot only after a completed scrape prevents overlap and
    catch-up queues. A backward system-clock correction recalculates the target;
    a forward correction past the target wakes one cycle, never a backlog.
    """
    if stop.is_set():
        return
    if clock is None:
        clock = lambda: datetime.now(timezone.utc)
    previous = clock().astimezone(timezone.utc)
    target = next_poll_at(previous, interval, timezone_name)
    health.update(next_poll_at=target.isoformat())
    LOGGER.info("Next dashboard scrape at %s", target.astimezone(ZoneInfo(timezone_name)).isoformat())
    while not stop.is_set():
        current = clock().astimezone(timezone.utc)
        if current < previous:
            target = next_poll_at(current, interval, timezone_name)
            health.update(next_poll_at=target.isoformat())
        previous = current
        remaining = (target - current).total_seconds()
        if remaining <= 0:
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=min(10, remaining))
        except asyncio.TimeoutError:
            health.update()
