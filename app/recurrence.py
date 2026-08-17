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
            status_code=400,
            detail=(f"Cannot schedule recurrent shift with period {period},"
                    f" but without duration, repeat or end date.")
        )

    print(f"DEBUG: recurrence_maker after validation  {shift.worker_id=}, {period=}, {duration=}, {repeat=}, {end_date=})")
    shifts_list: list[ShiftCreate] = []
    new_shift: ShiftCreate | None = None
    days, weeks = parse(period)
    r_days, r_weeks = parse(duration)
    if (days, weeks) == (-1,-1) or (r_days, r_weeks) == (-1,-1):
        raise HTTPException(
            status_code=400,
            detail=(f"Cannot schedule recurrent shift with period {period},"
                    f" and duration {duration}.")
        )
    print(f"DEBUG: recurrence_maker parsed {period=} ({days=}, {weeks=})  "
          f" {duration=} ({r_days=}, {r_weeks=}).")
    # DEBUG initial content matching test
    # if period in ['week', 'weekly']:
    #     if duration == '2 months':
    # TODO: We need to solve number of days and weeks for limit date and increment
    start_time = shift.start_time
    end_time = shift.end_time
    limit_date = start_time + timedelta(weeks=r_days*r_weeks)
    new_start_time = start_time
    new_end_time = end_time
    while new_start_time < limit_date:
        new_start_time = new_start_time + timedelta(days=days, weeks=weeks)
        new_end_time = new_end_time + timedelta(days=days, weeks=weeks)
        new_shift = ShiftCreate(worker_id=shift.worker_id, start_time=new_start_time, end_time=new_end_time)

        if new_shift is None:
            print(f"DEBUG: recurrence_maker no recurrence asked for shift={shift}")
            return None
        conflicts = find_conflicting_shifts(session, new_shift.worker_id, new_shift.start_time, new_shift.end_time)
        print(f"DEBUG: recurrence_maker conflicts={conflicts}")
        print(f"DEBUG: recurrence_maker return new shift:"
              f" {new_shift.worker_id}, {new_shift.start_time}, {new_shift.end_time}")
        # Don't add the shift if conflicted
        if len(conflicts) == 0:
            shifts_list.append(new_shift)

    return shifts_list

def parse(time_block: str):
    """
    Examples:
    Period: [ "daily", "weekly", "5days", "biweekly", "monthly", "quarterly", "yearly"]
    Duration: ["day", "week", "month", "year"]
    Allows:   [ "1 day", "X days", "1 week", "X weeks", "1 month", "X months", "1 year", "X years"]
    """
    """
    (1, 0) = parse('daily') = parse("1 day")
    (2, 0) = parse("2 days")
    (3, 0) = parse("3 days")
    (4, 0) = parse("4 days")
    (5, 0) = parse("5 days")
    (6, 0) = parse("6 days")
    (7, 0) = parse("7 days")
    (0, 1) = parse('weekly') = parse("1 week")
    (5, 1) = parse('5days') == week of 5 days == Monday, Tuesday, Wednesday, Thursday, Friday
    (0, 2) = parse('biweekly') = parse("2 weeks")
    (0, 4) = parse('monthly')
    (0, 12) = parse('quarterly')
    (0, 48) = parse('yearly')
    
    """
    assert isinstance(time_block, str)
    from ast import literal_eval
    VALID_TBLOCKS = ["daily", "weekly", "5days", "biweekly", "monthly", "quarterly", "yearly",
                     "day", "days", "week", "weeks", "month", "months", "quarter", "quarters",
                     "year", "years"]
    in_block = time_block.strip().split(' ')
    if len(in_block) > 1:
        day = in_block[0]
        try:
            nday = literal_eval(day)
        except Exception as e:
            raise e
    else:
        nday = 0
    week = in_block[-1].lower()

    if week in VALID_TBLOCKS:
        if week in ["week", "weeks", "weekly", "5days"]:
            nweek = 1
        elif week in ["month", "months", "monthly"]:
            nweek = 4
        else:
            nweek = 0
    else:
        return -1, -1
    # TODO: Consider other cases and week days names (Monday, ...)
    return nday, nweek
