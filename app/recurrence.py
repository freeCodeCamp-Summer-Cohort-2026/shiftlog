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

VALID_TBLOCKS = ["daily", "weekly", "5days", "biweekly", "monthly", "quarterly", "yearly",
                 "day", "days", "week", "weeks", "month", "months", "quarter", "quarters",
                 "year", "years"]
WORKWEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
                "mondays", "tuesdays", "wednesdays", "thursdays", "fridays"]
WEEKENDDAYS = ["saturday", "sunday", "saturdays", "sundays"]
WEEKDAYS = WORKWEEKDAYS + WEEKENDDAYS
dict_weekday_num = {"monday":0, "tuesday":1, "wednesday":2, "thursday":3,
                    "friday":4, "saturday":5, "sunday":6}


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
    next_same_week_day = -1
    start_time = shift.start_time
    end_time = shift.end_time
    new_start_time = start_time
    new_end_time = end_time

    # Parse weekdays
    lc_period = period.strip().rstrip('s').lower()
    if lc_period in WEEKDAYS:
        num_weekday = dict_weekday_num[lc_period]
        # next_same_week_day = shift.start_time.strftime("%A").lower()
        new_start_time = start_time
        next_same_week_day = new_start_time.weekday()
        new_end_time = end_time

        while next_same_week_day != num_weekday:
            new_start_time += timedelta(days=1)
            next_same_week_day = new_start_time.weekday()
            new_end_time += timedelta(days=1)

        days, weeks = (0, 1)  # weekly period
    else:
        lc_period = -1  # This flags that weekday is not in use
        days, weeks = parse(period)
    r_days, r_weeks = parse(duration)
    if (days, weeks) == (-1,-1) or (r_days, r_weeks) == (-1,-1):
        raise HTTPException(
            status_code=400,
            detail=(f"Cannot schedule recurrent shift with period {period},"
                    f" and duration {duration}.")
        )

#    print(f"DEBUG: recurrence_maker parsed {period=} ({days=}, {weeks=})  "
#          f" {duration=} ({r_days=}, {r_weeks=}).")

    r_days = r_days if r_days >= 1 else 1
    limit_date = new_start_time + timedelta(weeks=r_days*r_weeks)
    while new_start_time < limit_date:
        if lc_period == -1:  # For numeric days and weeks
            new_start_time += timedelta(days=days, weeks=weeks)
            new_end_time += timedelta(days=days, weeks=weeks)
        new_shift = ShiftCreate(worker_id=shift.worker_id, start_time=new_start_time, end_time=new_end_time)
        if lc_period != -1:  # For weekdays
            new_start_time += timedelta(days=days, weeks=weeks)
            new_end_time += timedelta(days=days, weeks=weeks)

        if new_shift is None:
            print(f"DEBUG: recurrence_maker no recurrence asked for shift={shift}")
            return None
        conflicts = find_conflicting_shifts(session, new_shift.worker_id, new_shift.start_time, new_shift.end_time)
        print(f"DEBUG: recurrence_maker conflicts={conflicts}")
        # print(f"DEBUG: recurrence_maker return new shift:"
        #       f" {new_shift.worker_id}, {new_shift.start_time}, {new_shift.end_time}")
        # TODO: How to report not created shifts?
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
    (1, 0) = parse('daily') = parse("1 day")  # Means continuous period of one day
    (2, 0) = parse("2 days")  # Means alternating periods of two days shifts, two days blank
    (3, 0) = parse("3 days")  # Means alternating periods of three days shifts, three days blank
    (4, 0) = parse("4 days")  # Means alternating periods of four days shifts, four days blank
    (5, 0) = parse("5 days")  # Means alternating periods of five days shifts, five days blank
    (6, 0) = parse("6 days")  # Means alternating periods of six days shifts, six days blank
    (7, 0) = parse("7 days")  # Means alternating periods of seven days shifts, seven days blank
    (0, 1) = parse('weekly') = parse("1 week")
    (5, 1) = parse('5days') == week of 5 days == Monday, Tuesday, Wednesday, Thursday, Friday
    (0, 2) = parse('biweekly') = parse("2 weeks")
    (0, 4) = parse('monthly') = parse("4 weeks")
    (0, 12) = parse('quarterly')
    (0, 48) = parse('yearly')
    
    """
    assert isinstance(time_block, str)
    from ast import literal_eval

    in_block = time_block.strip().split(' ')
    if len(in_block) > 1:
        day = in_block[0]
        try:
            nday = literal_eval(day)  # TODO: Parse numbers in text mode
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
