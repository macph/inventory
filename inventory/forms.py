"""
Forms for inventory models

"""
from datetime import timedelta

from django.core.exceptions import ValidationError
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

from .models import DP_QUANTITY, Item, MAX_DIGITS, Record, Unit, UnitEnum

MIN_DOUBLE_POST = timedelta(minutes=1)


def decimal_field(**kwargs):
    return DecimalField(
        min_value=0,
        max_digits=MAX_DIGITS,
        decimal_places=DP_QUANTITY,
        widget=TextInput(
            attrs={"inputmode": "decimal", "pattern": "^$|([0-9]+.?[0-9]*)|(.[0-9]+)"}
        ),
        **kwargs,
    )


class AddItemForm(ModelForm):
    class Meta:
        model = Item
        fields = ("name", "unit", "minimum", "initial")

    # override widget to be text input (TextField uses textarea)
    name = CharField(max_length=256)
    unit = ChoiceField()
    minimum = decimal_field(required=False)
    initial = decimal_field(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._units = Unit.objects.order_by("pk").all()

        def collect_units(unit):
            label = unit.label
            pairs = tuple((u.pk, u.symbol) for u in self._units if u.measure == unit)
            return label, pairs

        self.fields["unit"].choices = list(map(collect_units, UnitEnum))
        self.fields["unit"].initial = self._units[0].pk

    def clean_name(self):
        name = self.cleaned_data["name"]
        # the slug must also be unique, check before saving new model
        if Item.objects.filter(ident=slugify(name)).exists():
            raise ValidationError(f"Item name already exists.", code="invalid")
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

    def save(self, commit=True):
        with atomic():
            instance = super().save(commit)
            initial = self.cleaned_data["initial"]
            if initial and commit:
                quantity = round(initial * instance.unit.convert, DP_QUANTITY)
                new_record = Record(item=instance, quantity=quantity, note="initial")
                new_record.save()

        return instance


class EditItemForm(ModelForm):
    class Meta:
        model = Item
        fields = ("name", "unit", "minimum")
        exclude = ("ident",)

    # override widget to be text input (TextField uses textarea)
    name = CharField(max_length=256)
    unit = ModelChoiceField(None, empty_label=None)
    minimum = decimal_field(required=False)

    def __init__(self, *args, **kwargs):
        if "original" in kwargs:
            item = kwargs.pop("original")
        else:
            item = None

        super().__init__(*args, **kwargs)

        if item is not None:
            # set initial data to original item data, and restrict group of units
            self.fields["name"].initial = item.name
            self.fields["unit"].initial = item.unit.pk
            self.fields["unit"].queryset = Unit.objects.filter(
                measure=item.unit.measure
            )
            self.fields["minimum"].initial = item.minimum
        else:
            self.fields["unit"].queryset = Unit.objects.all()


class AddRecordForm(ModelForm):
    class Meta:
        model = Record
        exclude = ("item", "added")

    quantity = decimal_field()
    unit = ModelChoiceField(None, empty_label=None)

    def __init__(self, *args, **kwargs):
        item = kwargs.pop("parent_item")

        super().__init__(*args, **kwargs)

        self.parent_item = item
        self.fields["unit"].initial = item.unit.pk
        self.fields["unit"].queryset = Unit.objects.filter(measure=item.unit.measure)

    def clean(self):
        unit = self.cleaned_data["unit"]
        quantity = self.cleaned_data.get("quantity")
        if quantity is None:
            return super().clean()

        if self.parent_item.unit.measure != unit.measure:
            raise ValidationError(
                "Record must have same base unit of measurement as item", code="invalid"
            )

        # convert quantity to base unit
        self.cleaned_data["quantity"] = round(quantity * unit.convert, DP_QUANTITY)

        return super().clean()

    def save(self, commit=True):
        added = now()
        with atomic():
            if (
                self.parent_item.latest_record
                and added - self.parent_item.latest_record.added < MIN_DOUBLE_POST
            ):
                # modify latest record
                instance = self.parent_item.latest_record
                instance.added = added
                instance.quantity = self.instance.quantity
                if commit:
                    instance.save()
            else:
                # create new record
                instance = super().save(commit)

            unit = self.cleaned_data["unit"]
            if commit and self.parent_item.unit != unit:
                # Set item preferred unit to latest
                self.parent_item.unit = unit
                self.parent_item.save()

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
            if added - item.latest_record.added < MIN_DOUBLE_POST:
                # update latest record for item
                instance = item.latest_record
                instance.added = added
                instance.quantity = this.cleaned_data["values"][item.ident]
                updated_records.append(instance)
            else:
                # create new record for item
                instance = Record(
                    item=item,
                    quantity=this.cleaned_data["values"][item.ident],
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
