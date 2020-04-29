"""
Inventory admin configuration

"""
from django.contrib.admin import ModelAdmin, register
from django.db.models import TextField
from django.forms import ModelForm, TextInput

from .models import PresetItem, Unit, Item, Record


@register(PresetItem)
class PresetItemAdmin(ModelAdmin):
    formfield_overrides = {TextField: {"widget": TextInput}}
    list_display = ("name", "measure")


class UnitAdminForm(ModelForm):
    class Meta:
        model = Unit
        fields = "__all__"

    def clean(self):
        # Force 'plural' field to be None if empty
        if not self.cleaned_data["plural"]:
            self.cleaned_data["plural"] = None
        return super().clean()


@register(Unit)
class UnitAdmin(ModelAdmin):
    form = UnitAdminForm
    formfield_overrides = {TextField: {"widget": TextInput}}
    list_display = ("symbol", "measure", "convert")


@register(Item)
class ItemAdmin(ModelAdmin):
    formfield_overrides = {TextField: {"widget": TextInput}}
    list_display = ("user", "name", "unit", "added")


@register(Record)
class RecordAdmin(ModelAdmin):
    formfield_overrides = {TextField: {"widget": TextInput}}
    list_display = ("item", "quantity", "added")
