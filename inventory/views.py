"""
Inventory views

"""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.transaction import atomic
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.generic import View

from . import forms, models
from .operations import find_average_use


# TODO: Functionality to add extra items in an update form
# TODO: Convert between wider range of units, possibly with some sort of conversion
# TODO: Add multiple non-formal units such as 330 ml bottles or 400g tins


@login_required
def index(request):
    items = models.Item.with_latest_record().filter(user=request.user)
    find_average_use(items)
    return render(request, "index.html", {"list_items": items})


def records(request, ident=None):
    if not request.user.is_authenticated:
        return HttpResponse("Unauthorised", status=401)

    items = models.Item.with_records(asc=True).filter(user=request.user)
    if ident is not None:
        items = items.filter(ident=ident).all()
        if not items:
            raise Http404(f"food item {ident!r} not found")
    else:
        items = items.all()

    find_average_use(items)

    array = []
    for i in items:
        d_item = {
            "name": i.name,
            "ident": i.ident,
            "min": i.minimum,
            "avg": i.average,
            "records": [{"q": r.quantity, "a": r.added} for r in i.records.all()],
        }
        array.append(d_item)

    data = {"items": array}

    return JsonResponse(data)


class AddItem(LoginRequiredMixin, View):
    def get(self, request):
        new_item = forms.AddItemForm()
        initial_record = forms.AddInitialRecord()
        return render(
            request, "item_add.html", {"new_item": new_item, "record": initial_record}
        )

    def post(self, request):
        new_item = forms.AddItemForm(request.POST)
        initial_record = forms.AddInitialRecord(request.POST)

        if not (new_item.is_valid() and initial_record.is_valid()):
            return render(
                request,
                "item_add.html",
                {"new_item": new_item, "record": initial_record},
            )

        with atomic():
            new_item = new_item.save(commit=False)
            new_item.user = request.user
            new_item.save()
            record = initial_record.save(commit=False)
            if record.quantity is not None:
                # normalise quantity using new item's unit
                record.item = new_item
                record.quantity = round(
                    record.quantity * new_item.unit.convert, models.DP_QUANTITY
                )
                record.note = "initial"
                record.save()

        if request.POST.get("another"):
            # return blank form for adding new item
            next_item = forms.AddItemForm()
            next_record = forms.AddInitialRecord()
            return render(
                request,
                "item_add.html",
                {
                    "new_item": next_item,
                    "record": next_record,
                    "just_added": new_item.name,
                },
            )
        else:
            # go to new item page
            return redirect(new_item)


class GetItem(LoginRequiredMixin, View):
    def get(self, request, ident):
        # leave flexible to allow for manual URL input
        item = models.Item.with_records(delta=True).get(
            user=request.user, ident__iexact=slugify(ident)
        )
        if not item:
            return Http404(f"food item {ident!r} not found")
        elif item.ident != ident:
            # redirect to correct form of name
            return redirect("item_get", ident=item.ident)

        edit_item = forms.EditItemForm(original=item)
        add_record = forms.AddRecordForm(parent_item=item)
        return render(
            request,
            "item_get.html",
            {"item": item, "edit_item": edit_item, "add_record": add_record,},
        )

    def post(self, request, ident):
        # submitted via a POST form so we're expecting an exact match
        item = models.Item.with_records(delta=True).get(user=request.user, ident=ident)
        if not item:
            return Http404(f"food item {ident!r} not found")

        edit_item = forms.EditItemForm(request.POST, instance=item)
        if edit_item.is_valid():
            with atomic():
                updated_item = edit_item.save()
            # go to new item page
            return redirect(updated_item)
        else:
            add_record = forms.AddRecordForm(parent_item=item)
            return render(
                request,
                "item_get.html",
                {"item": item, "edit_item": edit_item, "add_record": add_record},
            )


class DeleteItem(LoginRequiredMixin, View):
    def get(self, request, ident):
        item = models.Item.objects.get(user=request.user, ident=ident)
        if not item:
            return Http404(f"food item {ident!r} not found")

        return render(request, "item_delete.html", {"item": item})

    def post(self, request, ident):
        item = models.Item.objects.get(user=request.user, ident=ident)
        if not item:
            return Http404(f"food item {ident!r} not found")

        with atomic():
            item.delete()

        return redirect("index")


class AddRecord(LoginRequiredMixin, View):
    def post(self, request, ident):
        # submitted via a POST form so we're expecting an exact match
        item = models.Item.with_latest_record().get(user=request.user, ident=ident)
        if not item:
            return Http404(f"food item {ident!r} not found")

        new_record = forms.AddRecordForm(request.POST, parent_item=item)
        if new_record.is_valid():
            # assign foreign key manually and update item if unit was changed
            with atomic():
                record = new_record.save(commit=False)
                record.item = item
                record.save()
                item.save()
            # go to item page
            return redirect(item)
        else:
            edit_item = forms.EditItemForm()
            return render(
                request,
                "item_get.html",
                {"item": item, "edit_item": edit_item, "add_record": new_record},
            )


class Update(LoginRequiredMixin, View):
    def get(self, request):
        items = models.Item.with_latest_record().filter(user=request.user)
        to_update = forms.generate_update_form(items)()
        return render(request, "update.html", {"update": to_update})

    def post(self, request):
        items = models.Item.with_latest_record().filter(user=request.user)
        to_update = forms.generate_update_form(items)(request.POST)
        if to_update.is_valid():
            to_update.save()
        return redirect("index")
