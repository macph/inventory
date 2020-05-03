"""
Forms for inventory models

"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.transaction import atomic
from django.forms import (
    BaseForm,
    CharField,
    ChoiceField,
    DecimalField,
    ModelChoiceField,
    ModelForm,
    Textarea,
    TextInput,
)
from django.utils.text import slugify
from django.utils.timezone import now

from .models import (
    format_quantity,
    Item,
    Record,
    Unit,
    UnitEnum,
    DP_QUANTITY,
    MAX_DIGITS,
)

MIN_DOUBLE_POST = timedelta(minutes=1)


class DecimalInput(TextInput):
    def __init__(self, attrs=None):
        to_add = {"inputmode": "decimal", "pattern": "^$|([0-9]+.?[0-9]*)|(.[0-9]+)"}
        new_attrs = attrs.update(to_add) if attrs else to_add
        super().__init__(new_attrs)


class CustomDecimalField(DecimalField):
    def prepare_value(self, value):
        if isinstance(value, str) or value is None:
            return value
        elif value:
            return format_quantity(value)
        else:
            return ""


def decimal_field(**kwargs):
    return CustomDecimalField(
        min_value=0,
        max_digits=MAX_DIGITS,
        decimal_places=DP_QUANTITY,
        widget=DecimalInput(),
        **kwargs,
    )


class AddItemForm(ModelForm):
    class Meta:
        model = Item
        fields = ("name", "unit", "minimum")

    # override widget to be text input (TextField uses textarea)
    name = CharField(max_length=256)
    unit = ChoiceField()
    minimum = decimal_field(required=False)
    initial = decimal_field(required=False)

    def __init__(self, *args, **kwargs):
        self._user = kwargs.pop("user")
        self._units = Unit.objects.order_by("pk").all()
        super().__init__(*args, **kwargs)

        def collect_units(unit):
            label = unit.label
            pairs = tuple((u.pk, u.symbol) for u in self._units if u.measure == unit)
            return label, pairs

        self.fields["unit"].choices = list(map(collect_units, UnitEnum))
        self.fields["unit"].initial = self._units[0].pk

    def clean_name(self):
        name = self.cleaned_data["name"]
        ident = slugify(name)
        # the slug must also be unique, check before saving new model
        if Item.objects.filter(Q(name=name) | Q(ident=ident), user=self._user).exists():
            raise ValidationError("Item name already exists.")
        return name

    def clean_unit(self):
        pk = int(self.cleaned_data["unit"])
        for unit in self._units:
            if pk == unit.pk:
                return unit
        else:
            raise ValidationError("Unit of measurement does not exist")

    def clean_minimum(self):
        return self.cleaned_data["minimum"] or 0


class AddInitialRecord(ModelForm):
    class Meta:
        model = Record
        fields = ("quantity",)

    quantity = decimal_field(required=False, label="Initial")


class EditItemForm(ModelForm):
    class Meta:
        model = Item
        fields = ("name", "unit", "minimum")

    # override widget to be text input (TextField uses textarea)
    name = CharField(max_length=256)
    unit = ModelChoiceField(None, empty_label=None)
    minimum = decimal_field(required=False)

    def __init__(self, *args, **kwargs):
        assert "instance" in kwargs, "original item expected"
        super().__init__(*args, **kwargs)

        # set initial data to original item data, and restrict group of units
        self.fields["name"].initial = self.instance.name
        unit = self.instance.unit
        self.fields["unit"].initial = unit.pk
        self.fields["unit"].queryset = Unit.objects.filter(measure=unit.measure)
        self.fields["minimum"].initial = self.instance.minimum / unit.convert

    def clean_name(self):
        name = self.cleaned_data["name"]
        # the slug must also be unique, check before saving new model
        if (
            Item.objects.filter(
                Q(name=name) | Q(ident=slugify(name)), user=self.instance.user
            )
            .exclude(id=self.instance.id)
            .exists()
        ):
            raise ValidationError("Item name already exists.")
        return name

    def clean(self):
        unit = self.cleaned_data.get("unit")
        if unit is None:
            raise ValidationError(
                "Record must have same base unit of measurement as item"
            )
        minimum = self.cleaned_data["minimum"] or 0
        normalised = minimum * self.cleaned_data["unit"].convert
        self.cleaned_data["minimum"] = round(normalised, DP_QUANTITY)

        return super().clean()


class AddRecordForm(ModelForm):
    class Meta:
        model = Record
        exclude = ("item", "added")

    quantity = decimal_field()
    unit = ModelChoiceField(None, empty_label=None)

    def __init__(self, *args, **kwargs):
        item = kwargs.pop("parent_item")

        super().__init__(*args, **kwargs)

        self._parent_item = item
        self.fields["unit"].initial = item.unit.pk
        self.fields["unit"].queryset = Unit.objects.filter(measure=item.unit.measure)

    def clean(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is None:
            return super().clean()

        unit = self.cleaned_data.get("unit")
        if unit is None or self._parent_item.unit.measure != unit.measure:
            raise ValidationError(
                "Record must have same base unit of measurement as item"
            )

        # convert quantity to base unit
        self.cleaned_data["quantity"] = round(quantity * unit.convert, DP_QUANTITY)

        return super().clean()

    def save(self, commit=True):
        added = now()
        with atomic():
            latest_record = (
                Record.objects.filter(item=self._parent_item).order_by("added").last()
            )
            if latest_record and added - latest_record.added < MIN_DOUBLE_POST:
                # modify latest record
                instance = latest_record
                instance.added = added
                instance.quantity = self.instance.quantity
                if commit:
                    instance.save()
            else:
                # create new record
                instance = super().save(commit=False)
                instance.item = self._parent_item
                instance.save()

        return instance


class UpdateItem:
    def __init__(self, ident, item, field):
        self.ident = ident
        self.item = item
        self.field = field

    def __repr__(self):
        return f"UpdateItem({self.ident!r}, {self.item!r}, {self.field!r})"


def generate_update_form(items):
    def append_prefix(name):
        return f"item-{name}"

    fields = {"note": CharField(widget=Textarea, required=False)}
    for i in items:
        # use a prefixed name so can be differentiated from other fields such as note
        fields[append_prefix(i.ident)] = decimal_field(required=False)

    def clean(this):
        # move all valid values into single dict
        this.cleaned_data["values"] = values = {}
        for item in this.items:
            name = append_prefix(item.ident)
            # it is possible the list of items will change between requests and so any
            # missing items should be ignored
            if name in this.cleaned_data:
                quantity = this.cleaned_data[name]
                if quantity is not None:
                    values[item.ident] = round(
                        quantity * item.unit.convert, DP_QUANTITY
                    )
                # remove the original value
                del this.cleaned_data[name]

        return this.cleaned_data

    def save(this):
        if this.errors:
            raise ValueError("Cannot save records because the data didn't validate.")
        added = now()
        new_records = []
        updated_records = []
        all_records = []
        for item in this.items:
            if item.ident not in this.cleaned_data["values"]:
                continue
            latest = item.latest_record
            if latest and added - latest.added < MIN_DOUBLE_POST:
                # update latest record for item
                instance = item.latest_record
                instance.added = added
                instance.quantity = this.cleaned_data["values"][item.ident]
                updated_records.append(instance)
            else:
                # create new record for item
                # set added timestamp as bulk_create does not call save() method
                instance = Record(
                    item=item,
                    quantity=this.cleaned_data["values"][item.ident],
                    added=added,
                    note=this.cleaned_data["note"],
                )
                new_records.append(instance)
            all_records.append(instance)

        with atomic():
            if new_records:
                Record.objects.bulk_create(new_records)
            if updated_records:
                Record.objects.bulk_update(
                    updated_records, fields=("added", "quantity")
                )

        return all_records

    def iter_items(this):
        for j in items:
            name = append_prefix(j.ident)
            yield UpdateItem(name, j, this[name])

    return type(
        "UpdateForm",
        (BaseForm,),
        {
            "base_fields": fields,
            "clean": clean,
            "save": save,
            "iter_items": iter_items,
            "items": items,
        },
    )
