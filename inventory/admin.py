"""
Inventory admin configuration

"""
from django.contrib import admin
from django.db import models
from django.forms import widgets

from .models import PresetItem, Unit, Item, Record


@admin.register(PresetItem)
class PresetItemAdmin(admin.ModelAdmin):
    formfield_overrides = {models.TextField: {"widget": widgets.TextInput}}
    list_display = ("name", "measure")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    formfield_overrides = {models.TextField: {"widget": widgets.TextInput}}
    list_display = ("symbol", "measure", "convert")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    formfield_overrides = {models.TextField: {"widget": widgets.TextInput}}
    list_display = ("name", "unit", "added")


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    formfield_overrides = {models.TextField: {"widget": widgets.TextInput}}
    list_display = ("item", "quantity", "added")
