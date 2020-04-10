"""
Inventory views

"""
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.generic import View

from . import forms, models


def index(request):
    items = models.Item.objects.prefetch_related("records").order_by("name")
    for i in items:
        i.get_latest_record()

    return render(request, "index.html", {"list_items": items})


class AddItemView(View):
    def get(self, request):
        form = forms.ItemForm()
        return render(request, "item_add.html", {"form": form})

    def post(self, request):
        new = forms.ItemForm(request.POST)
        if new.is_valid():
            new = new.save()
            if request.POST.get("another"):
                # return blank form for adding new item
                form = forms.ItemForm()
                return render(
                    request,
                    "item_add.html",
                    {"form": form, "just_added": new.name},
                )
            else:
                # go to new item page
                return redirect(new)
        else:
            return render(request, "item_add.html", {"form": new})


def item_get(request, ident):
    food = models.Item.objects.prefetch_related("unit", "records").get(
        ident__iexact=slugify(ident)
    )

    if not food:
        return Http404(f"food item {ident!r} not found")
    elif food.ident != ident:
        # redirect to correct form of name
        return redirect("item_get", ident=food.ident)
    else:
        food.all_records = food.records.all()
        return render(request, "item_get.html", {"food": food})


def item_update(request):
    pass


def item_delete(request, ident):
    pass
