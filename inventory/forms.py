"""
Forms for inventory models

"""
from django.forms import ModelForm, CharField

from . import models


class ItemForm(ModelForm):
    class Meta:
        model = models.Item
        fields = ("name", "unit", "minimum")
        exclude = ("ident",)

    # override widget to be text input (TextField uses textarea)
    name = CharField(max_length=256)
