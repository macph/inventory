"""
Inventory models

"""
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import (
    CheckConstraint,
    DateTimeField,
    DecimalField,
    ForeignKey,
    IntegerChoices,
    IntegerField,
    Model,
    Q,
    TextField,
    CASCADE,
    PROTECT,
)
from django.contrib.postgres.fields import CITextField
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.timezone import now

MAX_DIGITS = 12
DP_CONVERT = 6
DP_QUANTITY = 3


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
            CheckConstraint(
                check=Q(minimum__gte=0), name="check_item_minimum_not_negative"
            ),
        ]

    name = CITextField(max_length=256, unique=True)
    ident = TextField(unique=True)
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
        if not self.ident:
            self.ident = slugify(self.name)
        super().save(force_insert, force_update, using, update_fields)

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("item_get", args=(self.ident,))

    @cached_property
    def latest_record(self):
        try:
            return self.records.latest("added")
        except Record.DoesNotExist:
            return None

    def compatible_units(self):
        base = self.unit.measure
        return Unit.objects.filter(measure=base).all()


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
    added = DateTimeField(auto_now=True, db_index=True)
    note = TextField(blank=True)

    def __str__(self):
        return f"Record ({self.item.name}, {self.added})"

    def convert_quantity(self):
        return self.quantity / self.item.unit.convert

    def format_quantity(self):
        # truncate to 3 digits first
        # we use % formatting here as %g will truncate trailing zeros - {:g} won't
        return "%.*g" % (MAX_DIGITS, round(self.convert_quantity(), DP_QUANTITY))

    def print_quantity(self):
        quantity = self.convert_quantity()
        rounded = round(quantity, DP_QUANTITY)
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
