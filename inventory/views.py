"""
Inventory views

"""
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.generic import View

from . import forms, models


# TODO: Functionality to add extra items in an update form
# TODO: Separate forms for multiple objects
# TODO: Raw SQL queries to avoid n+1 queries
# TODO: Group choices by base measurement when posting items
# TODO: Add fancy graphs
# TODO: Convert between wider range of units, possibly with some sort of conversion
# TODO: Add multiple non-formal units such as 330 ml bottles or 400g tins
# TODO: Update latest record instead of adding within a small time period


def index(request):
    items = models.Item.objects.prefetch_related("records").order_by("name")
    for i in items:
        i.get_latest_record()

    return render(request, "index.html", {"list_items": items})


class AddItem(View):
    def get(self, request):
        form = forms.AddItemForm()
        return render(request, "item_add.html", {"form": form})

    def post(self, request):
        new_item = forms.AddItemForm(request.POST)
        if new_item.is_valid():
            new_item = new_item.save()
            if request.POST.get("another"):
                # return blank form for adding new item
                form = forms.AddItemForm()
                return render(
                    request,
                    "item_add.html",
                    {"form": form, "just_added": new_item.name},
                )
            else:
                # go to new item page
                return redirect(new_item)
        else:
            return render(request, "item_add.html", {"form": new_item})


class GetItem(View):
    def get(self, request, ident):
        # leave flexible to allow for manual URL input
        item = models.Item.objects.prefetch_related("unit", "records").get(
            ident__iexact=slugify(ident)
        )
        if not item:
            return Http404(f"food item {ident!r} not found")
        elif item.ident != ident:
            # redirect to correct form of name
            return redirect("item_get", ident=item.ident)

        edit_item = forms.EditItemForm(original=item)
        add_record = forms.AddRecordForm(parent_item=item)
        item.all_records = item.records.all()
        return render(
            request,
            "item_get.html",
            {"item": item, "edit_item": edit_item, "add_record": add_record},
        )

    def post(self, request, ident):
        # submitted via a POST form so we're expecting an exact match
        item = models.Item.objects.prefetch_related("unit", "records").get(ident=ident)
        if not item:
            return Http404(f"food item {ident!r} not found")

        updated_item = forms.EditItemForm(request.POST, instance=item)
        if updated_item.is_valid():
            updated_item = updated_item.save()
            # go to new item page
            return redirect(updated_item)
        else:
            add_record = forms.AddRecordForm(parent_item=item)
            item.all_records = item.records.all()
            return render(
                request,
                "item_get.html",
                {"item": item, "edit_item": updated_item, "add_record": add_record},
            )


class DeleteItem(View):
    def get(self, request, ident):
        item = models.Item.objects.get(ident=ident)
        if not item:
            return Http404(f"food item {ident!r} not found")

        return render(request, "item_delete.html", {"item": item})

    def post(self, request, ident):
        item = models.Item.objects.get(ident=ident)
        if not item:
            return Http404(f"food item {ident!r} not found")

        item.delete()

        return redirect("index")


class AddRecord(View):
    def post(self, request, ident):
        # submitted via a POST form so we're expecting an exact match
        item = models.Item.objects.prefetch_related("unit").get(ident=ident)
        if not item:
            return Http404(f"food item {ident!r} not found")

        new_record = forms.AddRecordForm(request.POST, parent_item=item)
        if new_record.is_valid():
            # assign foreign key manually
            new_record.save(commit=False)
            new_record.instance.item = item
            new_record.save()
            # go to item page
            return redirect(item)
        else:
            edit_item = forms.EditItemForm()
            item.all_records = item.records.all()
            return render(
                request,
                "item_get.html",
                {"item": item, "edit_item": edit_item, "add_record": new_record},
            )


class Update(View):
    def get(self, request):
        items = models.Item.objects.prefetch_related("records").order_by("name")
        for i in items:
            i.get_latest_record()
        to_update = forms.generate_update_form(items)()
        return render(request, "update.html", {"update": to_update})

    def post(self, request):
        items = models.Item.objects.prefetch_related("records").order_by("name")
        to_update = forms.generate_update_form(items)(request.POST)
        if to_update.is_valid():
            to_update.save()
        return redirect("index")
