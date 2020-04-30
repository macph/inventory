"""
Tests for datetime functions.

"""
from datetime import timedelta, datetime, date, time
from unittest import TestCase

from django.utils.timezone import get_default_timezone, now

from ..common import natural, since


DATE = date(2020, 4, 30)
TIME = time(12, 50, 0)


class NaturalTestCase(TestCase):
    DIFF_DATE_ONLY = [
        (-timedelta(days=121 + 365), "December 2018"),
        (-timedelta(days=121 + 364), "last January"),
        (-timedelta(days=121), "last December"),
        (-timedelta(days=120), "1 January"),
        (-timedelta(days=11), "19 April"),
        (-timedelta(days=10), "last Monday"),
        (-timedelta(days=4), "last Sunday"),
        (-timedelta(days=2), "Tuesday"),
        (-timedelta(days=1), "yesterday"),
        (timedelta(seconds=0), "today"),
        (timedelta(days=1), "tomorrow"),
        (timedelta(days=2), "Saturday"),
        (timedelta(days=4), "next Monday"),
        (timedelta(days=10), "next Sunday"),
        (timedelta(days=11), "11 May"),
        (timedelta(days=245), "31 December"),
        (timedelta(days=246), "next January"),
        (timedelta(days=246 + 364), "next December"),
        (timedelta(days=246 + 365), "January 2022"),
    ]

    DIFF_WITH_TIME = [
        (-timedelta(days=121 + 365), "December 2018"),
        (-timedelta(days=121 + 364), "last January"),
        (-timedelta(days=121), "last December"),
        (-timedelta(days=120), "1 January 12:50"),
        (-timedelta(days=11), "19 April 12:50"),
        (-timedelta(days=10), "last Monday 12:50"),
        (-timedelta(days=4), "last Sunday 12:50"),
        (-timedelta(days=2), "Tuesday 12:50"),
        (-timedelta(days=1), "yesterday 12:50"),
        (-timedelta(minutes=90), "11:20"),
        (timedelta(seconds=0), "12:50"),
        (timedelta(minutes=90), "14:20"),
        (timedelta(days=1), "tomorrow 12:50"),
        (timedelta(days=2), "Saturday 12:50"),
        (timedelta(days=4), "next Monday 12:50"),
        (timedelta(days=10), "next Sunday 12:50"),
        (timedelta(days=11), "11 May 12:50"),
        (timedelta(days=245), "31 December 12:50"),
        (timedelta(days=246), "next January"),
        (timedelta(days=246 + 364), "next December"),
        (timedelta(days=246 + 365), "January 2022"),
    ]

    @classmethod
    def setUpClass(cls):
        cls.tz = get_default_timezone()
        cls.date = DATE
        cls.dt = datetime.combine(DATE, TIME).astimezone(cls.tz)

    def test_tz(self):
        self.assertEqual(str(self.tz), "Europe/London")

    def test_natural_date_only(self):
        for diff, expected in self.DIFF_DATE_ONLY:
            with self.subTest(e=expected):
                self.assertEqual(natural(self.date + diff, self.date), expected)

    def test_natural_with_time(self):
        for diff, expected in self.DIFF_WITH_TIME:
            with self.subTest(e=expected):
                self.assertEqual(natural(self.dt + diff, self.dt), expected)


class TimeSinceTestCase(TestCase):
    DIFF_DATE_ONLY = [
        (-timedelta(days=700), "2 years ago"),
        (-timedelta(days=371), "a year ago"),
        (-timedelta(days=354), "12 months ago"),
        (-timedelta(days=55), "2 months ago"),
        (-timedelta(days=31), "a month ago"),
        (-timedelta(days=30), "4 weeks ago"),
        (-timedelta(days=7), "a week ago"),
        (-timedelta(days=6), "6 days ago"),
        (-timedelta(days=1), "yesterday"),
        (timedelta(days=0), "today"),
        (timedelta(days=1), "tomorrow"),
        (timedelta(days=6), "6 days"),
        (timedelta(days=7), "a week"),
        (timedelta(days=29), "4 weeks"),
        (timedelta(days=30), "a month"),
        (timedelta(days=55), "2 months"),
        (timedelta(days=354), "12 months"),
        (timedelta(days=371), "a year"),
        (timedelta(days=700), "2 years"),
    ]

    DIFF_WITH_TIME = [
        (-timedelta(days=700), "2 years ago"),
        (-timedelta(days=371), "a year ago"),
        (-timedelta(days=354), "12 months ago"),
        (-timedelta(days=55), "2 months ago"),
        (-timedelta(days=31), "a month ago"),
        (-timedelta(days=30, hours=22), "4 weeks ago"),
        (-timedelta(days=7, hours=1), "a week ago"),
        (-timedelta(days=6, hours=22), "7 days ago"),
        (-timedelta(hours=24), "a day ago"),
        (-timedelta(hours=23, minutes=45), "24 hours ago"),
        (-timedelta(hours=1), "an hour ago"),
        (-timedelta(minutes=59, seconds=45), "60 minutes ago"),
        (-timedelta(seconds=105), "2 minutes ago"),
        (-timedelta(seconds=75), "a minute ago"),
        (-timedelta(seconds=30), "just now"),
        (timedelta(seconds=0), "now"),
        (timedelta(seconds=30), "now"),
        (timedelta(seconds=75), "a minute"),
        (timedelta(seconds=105), "2 minutes"),
        (timedelta(minutes=59, seconds=45), "60 minutes"),
        (timedelta(hours=1), "an hour"),
        (timedelta(hours=23, minutes=45), "24 hours"),
        (timedelta(hours=24), "a day"),
        (timedelta(days=6, hours=22), "7 days"),
        (timedelta(days=7, hours=1), "a week"),
        (timedelta(days=29, hours=22), "4 weeks"),
        (timedelta(days=30), "a month"),
        (timedelta(days=55), "2 months"),
        (timedelta(days=354), "12 months"),
        (timedelta(days=371), "a year"),
        (timedelta(days=700), "2 years"),
    ]

    @classmethod
    def setUpClass(cls):
        cls.tz = get_default_timezone()
        cls.date = DATE
        cls.dt = datetime.combine(DATE, TIME).astimezone(cls.tz)

    def test_tz(self):
        self.assertEqual(str(self.tz), "Europe/London")

    def test_now(self):
        self.assertEqual(since(self.dt), since(self.dt, now()))

    def test_no_mixed_dates(self):
        with self.assertRaises(TypeError):
            _ = since(self.dt, self.date)

    def test_since_date_only(self):
        for diff, expected in self.DIFF_DATE_ONLY:
            with self.subTest(e=expected):
                self.assertEqual(since(self.date + diff, self.date), expected)

    def test_since_with_date(self):
        for diff, expected in self.DIFF_WITH_TIME:
            with self.subTest(e=expected):
                self.assertEqual(since(self.dt + diff, self.dt), expected)

    def test_since_day_behind_tz(self):
        earlier = datetime(2019, 10, 26, 8, 0, 0).astimezone(self.tz)
        later = datetime(2019, 10, 27, 7, 45, 0).astimezone(self.tz)
        self.assertEqual(since(earlier, later), "25 hours ago")
