"""
Tests for models.

"""
from decimal import Decimal
from unittest import TestCase

from ..models import format_quantity


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
