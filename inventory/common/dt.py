"""
Datetime utility functions

"""
from calendar import monthrange
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional

from django.utils.timezone import now as tz_now


def _calendar_delta(dt: date, years: int = 0, months: int = 0, days: int = 0) -> date:
    d = date(dt.year + years, dt.month, dt.day)
    if months != 0:
        delta = d.month - 1 + months
        # floor division, should work for positive and negative delta
        new_year = d.year + delta // 12
        # modulo will always be positive if the denominator is positive
        new_month = delta % 12 + 1
        # clamp day at max for that month and year
        _, num_days = monthrange(new_year, new_month)
        d = date(new_year, new_month, min(d.day, num_days))
    if days != 0:
        d = d + timedelta(days=days)

    if isinstance(dt, datetime):
        naive = datetime(d.year, d.month, d.day, dt.hour, dt.minute, dt.second)
        return naive.astimezone(dt.tzinfo)
    else:
        return d


def _calendar_count(
    first: date, second: date, years: int = 0, months: int = 0, days: int = 0
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


def since(then: date, now: Optional[date] = None) -> str:
    # check if this is date or datetime - if former, extract date from other
    # we want both to be the same
    other: date
    has_time = isinstance(then, datetime)
    if has_time and now is None:
        other = tz_now()
    elif has_time and isinstance(now, datetime):
        other = now
    elif has_time:
        raise TypeError("the latter argument must be a datetime to match the former")
    else:
        _now: date = now or tz_now()
        other = date(_now.year, _now.month, _now.day)

    if then >= other:
        past, first, second = False, other, then
    else:
        past, first, second = True, then, other

    diff = second - first

    if not has_time and not diff:
        return "today"
    if has_time and diff < timedelta(minutes=1):
        return "just now" if past else "now"

    ago = " ago" if past else ""

    if has_time and diff < timedelta(hours=1):
        minutes = round(diff.total_seconds() / 60)
        return f"a minute{ago}" if minutes == 1 else f"{minutes} minutes{ago}"

    if has_time and first > _calendar_delta(second, days=-1):
        hours = round(diff.total_seconds() / 3600)
        return f"an hour{ago}" if hours == 1 else f"{hours} hours{ago}"

    if not has_time and diff == timedelta(days=1):
        return "yesterday" if past else "tomorrow"

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
    return f"a year{ago}" if years == 1 else f"{years} years{ago}"


_ND_FORMATS = [
    ("%B %Y", "%B %Y"),
    ("last %B", "last %B"),
    ("%-d %B", "%-d %B %H:%M"),
    ("last %A", "last %A %H:%M"),
    ("%A", "%A %H:%M"),
    ("yesterday", "yesterday %H:%M"),
    ("today", "%H:%M"),
    ("tomorrow", "tomorrow %H:%M"),
    ("next %A", "next %A %H:%M"),
    ("next %B", "next %B"),
    ("%B %Y", "%B %Y"),
]


class _ND(Enum):
    YEAR_BEFORE = 0
    LAST_YEAR = 1
    THIS_YEAR = 2
    LAST_WEEK = 3
    THIS_WEEK = 4
    YESTERDAY = 5
    TODAY = 6
    TOMORROW = 7
    NEXT_WEEK = 8
    NEXT_YEAR = 9
    YEAR_AFTER = 10

    def format(self, dt: date) -> str:
        with_time = 1 if isinstance(dt, datetime) else 0
        return dt.strftime(_ND_FORMATS[self.value][with_time])


def _natural_date(then: date, now: Optional[date] = None) -> _ND:
    # Work on dates only
    then_d = date(then.year, then.month, then.day)
    _now = now or tz_now()
    now_d = date(_now.year, _now.month, _now.day)

    if then_d == now_d:
        return _ND.TODAY
    # Check if days are adjacent
    elif then_d == _calendar_delta(now_d, days=-1):
        return _ND.YESTERDAY
    elif then_d == _calendar_delta(now_d, days=1):
        return _ND.TOMORROW

    # calculate weeks before and after now and check if date lie within these ranges
    this_week = _calendar_delta(now_d, days=-now_d.weekday())
    last_week = _calendar_delta(this_week, days=-7)
    next_week = _calendar_delta(this_week, days=7)
    fortnight = _calendar_delta(this_week, days=14)
    if last_week <= then_d < this_week:
        return _ND.LAST_WEEK
    elif this_week <= then_d < next_week:
        return _ND.THIS_WEEK
    elif next_week <= then_d < fortnight:
        return _ND.NEXT_WEEK

    # check rest of year
    elif then_d.year < now_d.year - 1:
        return _ND.YEAR_BEFORE
    elif then_d.year == now_d.year - 1:
        return _ND.LAST_YEAR
    elif then_d.year == now_d.year + 1:
        return _ND.NEXT_YEAR
    elif then_d.year > now_d.year + 1:
        return _ND.YEAR_AFTER
    else:
        return _ND.THIS_YEAR


def natural(then: date, now: Optional[date] = None) -> str:
    return _natural_date(then, now).format(then)
