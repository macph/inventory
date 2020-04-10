"""
Inventory models

"""
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
from django.utils.text import slugify


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
    convert = DecimalField(max_digits=12, decimal_places=6)

    def __str__(self):
        return str(self.symbol)


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
    minimum = DecimalField(max_digits=12, decimal_places=3, default=0)
    added = DateTimeField(auto_now=True)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.ident:
            self.ident = slugify(self.name)
        super().save(force_insert, force_update, using, update_fields)

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("item_get", args=(self.ident,))

    def get_latest_record(self):
        try:
            self.latest_record = self.records.latest("added")
        except Record.DoesNotExist:
            self.latest_record = None

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
    quantity = DecimalField(max_digits=12, decimal_places=3)
    added = DateTimeField(auto_now=True, db_index=True)
    note = TextField(blank=True)

    def __str__(self):
        return f"Record ({self.item.name}, {self.added})"

    def print_quantity(self):
        unit = self.item.unit
        # Convert to base value to current unit
        in_unit = self.quantity / unit.convert

        quantity = f"{in_unit:.3g}"
        unit = str(self.item.unit.code)
        if unit:
            quantity += " " + unit

        return quantity
