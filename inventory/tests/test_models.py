"""
Tests for models.

"""
from decimal import Decimal
from unittest import TestCase

from .util import BaseTestCase
from ..models import format_quantity, Item, Record
from ..operations import find_average_use


class FormatQuantityTestCase(TestCase):
    DECIMAL = [
        ("0.000", "0", "+0"),
        ("1.000", "1", "+1"),
        ("100.000", "100", "+100"),
        ("1.234", "1.234", "+1.234"),
        ("-1.234", "−1.234", "−1.234"),
        ("1.2345", "1.235", "+1.235"),
        ("1.231", "1.23", "+1.23"),
        ("1.239", "1.24", "+1.24"),
        ("-1.999", "−2", "−2"),
        ("-1.001", "−1", "−1"),
        ("1.001", "1", "+1"),
        ("1.999", "2", "+2"),
    ]

    def test_format_quantity(self):
        for d, expected, _ in self.DECIMAL:
            with self.subTest(e=expected):
                self.assertEqual(format_quantity(Decimal(d), False), expected)

    def test_format_quantity_delta(self):
        for d, _, expected in self.DECIMAL:
            with self.subTest(e=expected):
                self.assertEqual(format_quantity(Decimal(d), True), expected)

    def test_is_nan(self):
        with self.assertRaises(ValueError):
            _ = format_quantity(Decimal("NaN"), False)

    def test_is_infinity(self):
        with self.assertRaises(ValueError):
            _ = format_quantity(Decimal("Infinity"), False)


class FoodItemTestCase(BaseTestCase):
    def test_no_latest_record(self):
        rice = Item.with_latest_record().get(user__username="john", name="rice")
        self.assertIsNone(rice.latest_record)

    def test_latest_record(self):
        butter = Item.with_latest_record().get(user__username="john", name="butter")

        self.assertEqual(
            butter.latest_record.added.isoformat(), "2020-04-14T08:27:39.282000+00:00"
        ),
        self.assertEqual(butter.latest_record.quantity, 2)

    def test_no_records(self):
        rice = Item.with_records().get(user__username="john", name="rice")
        self.assertEqual(list(rice.records.all()), [])

    def test_records(self):
        butter = Item.with_records().get(user__username="john", name="butter")
        records = butter.records.all()

        self.assertEqual(len(records), 8)
        latest = (
            Record.objects.filter(item__user__username="john", item__name="butter")
            .order_by("added")
            .last()
        )
        self.assertEqual(records[0], latest)

    def test_records_asc(self):
        butter = Item.with_records(asc=True).get(user__username="john", name="butter")
        records = list(butter.records.all())

        self.assertEqual(len(records), 8)
        latest = (
            Record.objects.filter(item__user__username="john", item__name="butter")
            .order_by("added")
            .last()
        )
        self.assertEqual(records[-1], latest)

    def test_records_delta(self):
        butter = Item.with_records(delta=True, asc=True).get(
            user__username="john", name="butter"
        )
        records = butter.records.all()

        self.assertEqual(
            [i.delta for i in records], [300, 700, 1000, -1000, -1000, 1000, 0, 1000],
        )

    def test_no_expected_end(self):
        rice = Item.with_latest_record().get(user__username="john", name="rice")
        find_average_use((rice,))

        self.assertIsNone(rice.expected_end())

    def test_expected_end(self):
        butter = Item.with_latest_record().get(user__username="john", name="butter")
        find_average_use((butter,))

        self.assertEqual(
            butter.expected_end().isoformat(), "2020-04-18T04:32:50.448000+00:00"
        )
