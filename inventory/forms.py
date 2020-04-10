"""
Forms for inventory models

"""
from django.core.exceptions import ValidationError
from django.forms import ModelChoiceField, ModelForm, CharField

from . import models


class AddItemForm(ModelForm):
    class Meta:
        model = models.Item
        fields = ("name", "unit", "minimum")
        exclude = ("ident",)

    # override widget to be text input (TextField uses textarea)
    name = CharField(max_length=256)


class EditItemForm(ModelForm):
    class Meta:
        model = models.Item
        fields = ("name", "unit", "minimum")
        exclude = ("ident",)

    # override widget to be text input (TextField uses textarea)
    name = CharField(max_length=256)
    unit = ModelChoiceField(None, empty_label=None)

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
            self.fields["unit"].queryset = models.Unit.objects.filter(
                measure=item.unit.measure
            )
            self.fields["minimum"].initial = item.minimum
        else:
            self.fields["unit"].queryset = models.Unit.objects.all()


class AddRecordForm(ModelForm):
    class Meta:
        model = models.Record
        exclude = ("item", "added")

    unit = ModelChoiceField(None, empty_label=None)

    def __init__(self, *args, **kwargs):
        item = kwargs.pop("parent_item")

        super().__init__(*args, **kwargs)

        self.parent_item = item
        self.fields["unit"].initial = item.unit.pk
        self.fields["unit"].queryset = models.Unit.objects.filter(
            measure=item.unit.measure
        )

    def clean(self):
        unit = self.cleaned_data["unit"]
        quantity = self.cleaned_data["quantity"]

        if self.parent_item.unit.measure != unit.measure:
            raise ValidationError(
                "Record must have same base unit of measurement as item", code="invalid"
            )

        # convert quantity to base unit
        self.cleaned_data["quantity"] = round(quantity * unit.convert, 3)
        # don't need unit any more
        del self.cleaned_data["unit"]

        return super().clean()
