"""
Forms for inventory models

"""
from django.core.exceptions import ValidationError
from django.forms import (
    BaseForm,
    CharField,
    DecimalField,
    ModelChoiceField,
    ModelForm,
    NumberInput,
    Textarea,
)
from django.utils.text import slugify

from .models import DP_QUANTITY, Item, MAX_DIGITS, Record, Unit


def decimal_field(required=True, **kwargs):
    return DecimalField(
        min_value=0,
        max_digits=MAX_DIGITS,
        decimal_places=DP_QUANTITY,
        required=required,
        widget=NumberInput(attrs=dict(min="0", step="1")),
        **kwargs,
    )


class AddItemForm(ModelForm):
    class Meta:
        model = Item
        fields = ("name", "unit", "minimum", "initial")

    # override widget to be text input (TextField uses textarea)
    name = CharField(max_length=256)
    minimum = decimal_field(False)
    initial = decimal_field(False)

    def clean_name(self):
        name = self.cleaned_data["name"]
        # the slug must also be unique, check before saving new model
        if Item.objects.filter(ident=slugify(name)).exists():
            raise ValidationError(f"Item name already exists.", code="invalid")
        return name

    def clean_minimum(self):
        return self.cleaned_data["minimum"] or 0

    def save(self, commit=True):
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
    minimum = decimal_field(False)

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
        quantity = self.cleaned_data["quantity"]

        if self.parent_item.unit.measure != unit.measure:
            raise ValidationError(
                "Record must have same base unit of measurement as item", code="invalid"
            )

        # convert quantity to base unit
        self.cleaned_data["quantity"] = round(quantity * unit.convert, DP_QUANTITY)
        # don't need unit any more
        del self.cleaned_data["unit"]

        return super().clean()


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
        records = []
        for item in this.items:
            if item.ident not in this.cleaned_data["values"]:
                continue
            new_record = Record(
                item=item,
                quantity=this.cleaned_data["values"][item.ident],
                note=this.cleaned_data["note"],
            )
            records.append(new_record)

        Record.objects.bulk_create(records)
        return records

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
