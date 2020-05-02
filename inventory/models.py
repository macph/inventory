"""
Inventory models

"""
from datetime import timedelta
from decimal import localcontext, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import (
    CheckConstraint,
    DateTimeField,
    DecimalField,
    F,
    ForeignKey,
    IntegerChoices,
    IntegerField,
    Model,
    Prefetch,
    Q,
    TextField,
    UniqueConstraint,
    Window,
    CASCADE,
    PROTECT,
)
from django.db.models.functions import Coalesce, Lag, Lead
from django.conf import settings
from django.contrib.postgres.fields import CITextField
from django.urls import reverse
from django.utils.text import slugify
from django.utils.timezone import now


MAX_DIGITS = 12
DP_CONVERT = 6
DP_QUANTITY = 3


def round_quantity(value):
    if not value.is_finite():
        raise ValueError(f"{value!r} not a finite number")
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_UP
        r0, r1 = round(value, DP_QUANTITY), round(value, DP_QUANTITY - 1)
        return r1 if abs(r1 - r0) <= 10 ** -DP_QUANTITY else r0


def format_quantity(value, delta=False):
    # pad with plus sign if delta
    fmt = "%+.*g" if delta else "%.*g"
    # truncate to 3 digits first
    # we use % formatting here as %g will truncate trailing zeros - {:g} won't
    # replace dash with real minus sign
    return (fmt % (MAX_DIGITS, round_quantity(value))).replace("-", "−")


class UnitEnum(IntegerChoices):
    """ Base unit of measurement. """

    GENERIC = 0
    LENGTH = 1
    MASS = 2
    VOLUME = 3


class PresetItem(Model):
    """ Preset food item to help user get started with adding food products. """

    name = CITextField(max_length=256, unique=True)
    measure = IntegerField(choices=UnitEnum.choices, null=True)

    def __str__(self):
        return f"{self.name} (preset)"


def validate_gt_zero(value):
    if value <= 0:
        raise ValidationError(f"{value} must be greater than zero")


class Unit(Model):
    """ Unit of measurement for each food product. """

    class Meta:
        constraints = [
            CheckConstraint(check=Q(convert__gt=0), name="check_unit_convert_positive"),
        ]

    symbol = CITextField(max_length=64, unique=True)
    plural = CITextField(max_length=64, unique=True, null=True, blank=True)
    code = CITextField(max_length=64, unique=True, null=True, blank=True)
    measure = IntegerField(choices=UnitEnum.choices)
    convert = DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=DP_CONVERT,
        validators=(validate_gt_zero,),
    )

    def __str__(self):
        return str(self.symbol)

    def display(self):
        return (
            self.code or self.plural or (self.symbol if self.symbol != "none" else "")
        )


class Item(Model):
    """ A food product being tracked. """

    class Meta:
        constraints = [
            UniqueConstraint(fields=["user", "name"], name="unique_item_user_name"),
            UniqueConstraint(fields=["user", "ident"], name="unique_item_user_ident"),
            CheckConstraint(
                check=Q(minimum__gte=0), name="check_item_minimum_not_negative"
            ),
        ]

    name = CITextField(max_length=256)
    ident = TextField()
    user = ForeignKey(settings.AUTH_USER_MODEL, related_name="items", on_delete=CASCADE)
    unit = ForeignKey("Unit", on_delete=PROTECT, default=1)
    minimum = DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=DP_QUANTITY,
        default=0,
        validators=(MinValueValidator(0),),
    )
    added = DateTimeField()

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.id:
            self.added = now()
        self.ident = slugify(self.name)
        super().save(force_insert, force_update, using, update_fields)

    def __str__(self):
        return str(self.name)

    @classmethod
    def with_records(cls, delta=False, asc=False):
        order = F("added").asc() if asc else F("added").desc()
        records = Record.objects.order_by(order)
        if delta:
            # add quantity delta between this and previous record
            # use lag or lead depending on order being used here
            adjacent = Window(
                expression=(Lag if asc else Lead)("quantity"),
                partition_by=F("item_id"),
                order_by=order,
            )
            expression = F("quantity") - Coalesce(adjacent, 0)
            records = records.annotate(delta=expression)

        return (
            cls.objects.order_by("name")
            .select_related("unit")
            .prefetch_related(Prefetch("records", records))
        )

    @classmethod
    def with_latest_record(cls):
        latest = Prefetch(
            "records",
            Record.objects.order_by("item_id", "-added").distinct("item_id"),
            "latest_records",
        )
        return (
            cls.objects.order_by("name").select_related("unit").prefetch_related(latest)
        )

    def get_absolute_url(self):
        return reverse("item_get", args=(self.ident,))

    @property
    def latest_record(self):
        records = getattr(self, "latest_records")
        return records[0] if records else None

    def expected_end(self):
        average = getattr(self, "average")
        # calculate expected end only if latest record exists with non-zero quantity
        if self.latest_record is not None and self.latest_record.quantity and average:
            days = float(self.latest_record.quantity / average)
            return self.latest_record.added + timedelta(days=days)
        else:
            return None


class Record(Model):
    """ Quantity of items added or removed at a set point in time. """

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(quantity__gte=0), name="check_item_quantity_not_negative"
            ),
        ]

    item = ForeignKey("Item", related_name="records", on_delete=CASCADE)
    quantity = DecimalField(
        max_digits=MAX_DIGITS, decimal_places=3, validators=(MinValueValidator(0),),
    )
    added = DateTimeField(db_index=True)
    note = TextField(blank=True)

    def __str__(self):
        return f"Record ({self.item.name}, {self.added})"

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.id:
            self.added = now()
        super().save(force_insert, force_update, using, update_fields)

    def convert_quantity(self):
        return self.quantity / self.item.unit.convert

    def format_quantity(self):
        return format_quantity(self.convert_quantity())

    def format_delta(self):
        return format_quantity(getattr(self, "delta"), delta=True)

    def print_quantity(self):
        quantity = self.convert_quantity()
        rounded = round_quantity(quantity)
        if self.item.unit.code:
            return "%.*g %s" % (MAX_DIGITS, rounded, self.item.unit.code)
        elif quantity != 1 and self.item.unit.plural:
            return "%.*g %s" % (MAX_DIGITS, rounded, self.item.unit.plural)
        elif quantity != 1 and self.item.unit.symbol != "none":
            return "%.*g %ss" % (MAX_DIGITS, rounded, self.item.unit.symbol)
        elif self.item.unit.symbol != "none":
            return "%.*g %s" % (MAX_DIGITS, rounded, self.item.unit.symbol)
        else:
            return "%.*g" % (MAX_DIGITS, rounded)
