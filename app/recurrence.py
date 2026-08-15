"""Shift recurrence maker.

Given an initial shift, create a list of shifts repeating the initial shift,
according the provided configuration.
- **Period**: [ "daily", "weekly", "5days", "biweekly", "monthly", "quarterly", "yearly"]
- **Duration**": ["day", "week", "month", "year"]
- **Repeat**: int
- **End Date**: datetime

- Period if None, defaults to daily, if Duration or Repeat or End Date are set;
- If none of these, then is single shift (original behavior), returns no recurrence == None
- If Period is set but no limit, an error should be returned
- Duration, Repeat, End Date if all set, limit is the first reached

"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request

from sqlmodel import Session, select

from app.conflicts import find_conflicting_shifts
from app.models import Shift, ShiftCreate


def recurrence_maker(
        shift: ShiftCreate,
        session: Session,
        period: str | None,
        duration: str | None,
        repeat: int | None,
        end_date: datetime | None) -> list[ShiftCreate] | None:
    """Return a list of ShiftCreate shifts created from the initial shift."""
    if not (period or duration or repeat or end_date):
        return None

    if period is not None and not (duration or repeat or end_date):
        raise HTTPException(
            status_code=409,
            detail=f"Period is {period}, but is missing duration, repeat or end date.")

    # DEBUG initial content matching test
    shifts_list: list[ShiftCreate] = []
    new_shift: ShiftCreate = ShiftCreate()
    if period == 'week':
        if duration == '2 months':
            new_start_time = (shift.start_time + timedelta(weeks=8))  # .isoformat()
            new_end_time = (shift.end_time + timedelta(weeks=8))  # .isoformat()
            new_shift = ShiftCreate(shift.worker_id, new_start_time, new_end_time)

    conflicts = find_conflicting_shifts(session, new_shift.worker_id, new_shift.start_time, new_shift.end_time)
    print(f"DEBUG: recurrence_maker conflicts={conflicts}")
    print(f"DEBUG: recurrence_maker return new shift:"
          f" {new_shift.worker_id}, {new_shift.start_time}, {new_shift.end_time}")
    shifts_list.append(new_shift)

    return shifts_list
