"""
Datetime utility functions

"""
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Optional

from django.utils.timezone import now as tz_now


# TODO: natural day & time, eg yesterday or next Monday


def _calendar_delta(
    dt: datetime, years: int = 0, months: int = 0, days: int = 0
) -> datetime:
    d = date(dt.year + years, dt.month, dt.day)

    if months != 0:
        delta = d.month + months
        # floor division, should work for positive and negative delta
        new_year = d.year + delta // 12
        # modulo will always be positive if denominator positive
        new_month = delta % 12
        # clamp day at max for that month and year
        num_days = monthrange(new_year, new_month)[1]
        d = date(new_year, new_month, min(d.day, num_days))
    if days != 0:
        d = d + timedelta(days=days)

    return datetime(
        d.year,
        d.month,
        d.day,
        dt.hour,
        dt.minute,
        dt.second,
        dt.microsecond,
        dt.tzinfo,
    )


def _calendar_count(
    first: datetime, second: datetime, years: int = 0, months: int = 0, days: int = 0
) -> int:
    assert first < second, "first datetime must be before second"

    count = 0
    previous = second
    after_first = _calendar_delta(first, years, months, days)
    while previous > after_first:
        previous = _calendar_delta(previous, -years, -months, -days)
        count += 1

    diff_s = (previous - first).total_seconds()
    day_s = (after_first - first).total_seconds()
    count += round(diff_s / day_s)

    return count


def since(then: datetime, now: Optional[datetime] = None) -> str:
    other = now or tz_now()

    if then >= other:
        past, first, second = False, other, then
    else:
        past, first, second = True, then, other

    diff = second - first
    ago = " ago" if past else ""

    if diff < timedelta(minutes=1):
        return "just now" if past else "now"

    if diff < timedelta(hours=1):
        minutes = round(diff.total_seconds() / 60)
        return f"a minute{ago}" if minutes == 1 else f"{minutes} minutes{ago}"

    if first > _calendar_delta(second, days=-1):
        hours = round(diff.total_seconds() / 3600)
        return f"a hour{ago}" if hours == 1 else f"{hours} hours{ago}"

    if first > _calendar_delta(second, days=-7):
        days = _calendar_count(first, second, days=1)
        return f"a day{ago}" if days == 1 else f"{days} days{ago}"

    if first > _calendar_delta(second, months=-1):
        weeks = _calendar_count(first, second, days=7)
        return f"a week{ago}" if weeks == 1 else f"{weeks} weeks{ago}"

    if first > _calendar_delta(second, years=-1):
        months = _calendar_count(first, second, months=1)
        return f"a month{ago}" if months == 1 else f"{months} months{ago}"

    years = _calendar_count(first, second, years=1)
    return f"a years{ago}" if years == 1 else f"{years} years{ago}"
