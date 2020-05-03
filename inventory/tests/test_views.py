"""
Tests for views.

"""
from datetime import timedelta
from decimal import Decimal

from .util import BaseTestCase
from ..models import Item, Record
from ..operations import find_average_use


class AuthTestCase(BaseTestCase):
    def test_try_logged_out(self):
        response = self.client.get("/", follow=True)
        self.assertRedirects(response, "/login/?next=/")

    def test_try_api_logged_out(self):
        response = self.client.get("/records", follow=True)
        self.assertEqual(response.status_code, 401)

    def test_log_in(self):
        self.assertTrue(self.client.login(username="john", password="password2"))

    def test_try_logged_in(self):
        self.client.login(username="john", password="password2")
        response = self.client.get("/", follow=True)

        self.assertEqual(len(response.redirect_chain), 0)

    def test_try_api_logged_in(self):
        self.client.login(username="john", password="password2")
        response = self.client.get("/records/", follow=True)

        self.assertEqual(response.status_code, 200)

    def test_logout(self):
        self.client.login(username="john", password="password2")
        self.client.logout()


class AddItemTestCase(BaseTestCase):
    def setUp(self):
        self.client.login(username="john", password="password2")

    def test_add_new_item(self):
        data = {"name": "new potatoes", "unit": 201, "minimum": ""}
        response = self.client.post("/item/", data, follow=True)

        self.assertRedirects(response, "/item/new-potatoes/")
        item = Item.objects.get(name="new potatoes", user__username="john")
        self.assertEqual(item.minimum, 0)

    def test_add_new_item_minimum(self):
        data = {"name": "new potatoes", "unit": 201, "minimum": 1}
        response = self.client.post("/item/", data, follow=True)

        self.assertRedirects(response, "/item/new-potatoes/")
        item = Item.objects.get(name="new potatoes", user__username="john")
        self.assertEqual(item.minimum, 1)

    def test_add_another_item(self):
        data = {"name": "new potatoes", "unit": 201, "another": "1"}
        response = self.client.post("/item/", data)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "<strong>New potatoes</strong> added.", response.content.decode("UTF-8")
        )
        self.assertTrue(
            Item.objects.filter(name="new potatoes", user__username="john").exists()
        )

    def test_add_name_different_user(self):
        data = {"name": "lager", "unit": 301}
        response = self.client.post("/item/", data, follow=True)

        self.assertRedirects(response, "/item/lager/")

    def test_add_with_record(self):
        data = {"name": "new potatoes", "unit": 201, "quantity": 1}
        response = self.client.post("/item/", data, follow=True)

        self.assertRedirects(response, "/item/new-potatoes/")
        records = Record.objects.filter(
            item__name="new potatoes", item__user__username="john"
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].quantity, 1)

    def test_add_existing_name(self):
        data = {"name": "tinned tomatoes", "unit": 1}
        response = self.client.post("/item/", data, follow=True)

        self.assertFormError(response, "new_item", "name", "Item name already exists.")

    def test_add_existing_ident(self):
        data = {"name": "tinned  tomatoes", "unit": 1}
        response = self.client.post("/item/", data, follow=True)

        self.assertFormError(response, "new_item", "name", "Item name already exists.")


class GetItemTestCase(BaseTestCase):
    def setUp(self):
        self.client.login(username="john", password="password2")

    def test_get_item(self):
        response = self.client.get("/item/tinned-mackerel/")
        self.assertEqual(response.status_code, 200)

    def test_get_item_slugify(self):
        response = self.client.get("/item/Tinned Mackerel", follow=True)
        self.assertRedirects(response, "/item/tinned-mackerel/", status_code=301)

    def test_with_records(self):
        response = self.client.get("/item/coriander/")
        content = response.content.decode("UTF-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Created 13 April 2020 17:30", content)
        self.assertIn(
            '<th data-column-type="float" data-column-name="quantity">Quantity (pack)'
            "</th>",
            content,
        )
        self.assertIn('<td data-column-key="3.000"><strong>3</strong></td>', content)
        self.assertIn('<td data-column-key="1.000">+1</td>', content)


class RecordDataTestCase(BaseTestCase):
    LAGER = {
        "name": "lager",
        "ident": "lager",
        "min": "0.000",
        "avg": "4.014601186312643828112000",
        "records": [
            {"q": "0.330", "a": "2020-04-11T11:47:00.320Z"},
            {"q": "10.000", "a": "2020-04-11T12:39:11.072Z"},
            {"q": "1.000", "a": "2020-04-12T07:53:28.962Z"},
            {"q": "3.000", "a": "2020-04-12T07:58:21.570Z"},
            {"q": "1.000", "a": "2020-04-12T13:12:22.124Z"},
            {"q": "0.660", "a": "2020-04-13T12:50:46.325Z"},
            {"q": "0.330", "a": "2020-04-13T17:00:06.336Z"},
            {"q": "6.000", "a": "2020-04-14T09:32:55.529Z"},
        ],
    }

    def test_all_items(self):
        self.client.login(username="jane", password="password1")
        response = self.client.get("/records/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        items = data["items"]
        self.assertEqual(len(items), 15)

        lager = next((r for r in items if r["name"] == "lager"), None)
        self.assertEqual(lager, self.LAGER)

    def test_lager_only(self):
        self.client.login(username="jane", password="password1")
        response = self.client.get("/records/lager/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        items = data["items"]
        self.assertEqual(items, [self.LAGER])

    def test_not_exists(self):
        self.client.login(username="john", password="password2")
        response = self.client.get("/records/lager/")

        self.assertEqual(response.status_code, 404)

    def test_no_average(self):
        coriander = Item.objects.get(user__username="john", name="coriander")
        find_average_use((coriander,))

        self.assertEqual(coriander.average, None)

    def test_with_average(self):
        pasta = Item.with_records(asc=True).get(name="pasta", user__username="jane")
        find_average_use((pasta,))

        records = list(pasta.records.all())
        self.assertEqual(len(records), 5)

        seconds = Decimal((records[-1].added - records[0].added).total_seconds())
        total = Decimal()
        for i in range(len(records) - 1):
            current = records[i].quantity
            lead = records[i + 1].quantity
            total += max(current - lead, 0)

        average = (total / seconds) * 86400

        self.assertAlmostEqual(pasta.average, average)

    def test_with_delta(self):
        pasta = Item.with_records(delta=True, asc=True).get(
            name="pasta", user__username="jane"
        )

        records = list(pasta.records.all())
        self.assertEqual(len(records), 5)

        deltas = []
        for i in range(len(records)):
            lag = records[i - 1].quantity if i > 0 else 0
            current = records[i].quantity
            deltas.append(current - lag)

        self.assertEqual([r.delta for r in records], deltas)


class EditItemTestCase(BaseTestCase):
    def setUp(self):
        self.client.login(username="john", password="password2")

    def test_edit_item(self):
        self.assertFalse(
            Item.objects.filter(
                user__username="john", name="tinned plum tomatoes"
            ).exists()
        )

        data = {"name": "tinned plum tomatoes", "unit": "2", "minimum": ""}
        response = self.client.post("/item/tinned-tomatoes/", data, follow=True)

        self.assertRedirects(response, "/item/tinned-plum-tomatoes/")

        tomatoes = Item.objects.select_related("unit").get(
            user__username="john", name="tinned plum tomatoes"
        )
        self.assertEqual(tomatoes.unit.pk, 2)
        self.assertEqual(tomatoes.minimum, 0)

    def test_edit_name_exists(self):
        data = {"name": "olive oil", "unit": "1", "minimum": "0"}
        response = self.client.post("/item/vegetable-oil/", data, follow=True)

        self.assertFormError(response, "edit_item", "name", "Item name already exists.")

    def test_edit_slug_exists(self):
        data = {"name": "olive  oil", "unit": "1", "minimum": "0"}
        response = self.client.post("/item/vegetable-oil/", data, follow=True)

        self.assertFormError(response, "edit_item", "name", "Item name already exists.")

    def test_edit_wrong_unit(self):
        data = {"name": "vegetable oil", "unit": "301", "minimum": "0"}
        response = self.client.post("/item/vegetable-oil/", data, follow=True)

        self.assertFormError(
            response,
            "edit_item",
            "unit",
            "Select a valid choice. That choice is not one of the available choices.",
        )


class AddRecordTestCase(BaseTestCase):
    def setUp(self):
        self.client.login(username="john", password="password2")

    def test_add_record(self):
        data = {"quantity": "4", "unit": "301"}
        response = self.client.post("/item/lemonade/record/", data, follow=True)

        self.assertRedirects(response, "/item/lemonade/", status_code=302)

        records = Record.objects.filter(
            item__user__username="john", item__name="lemonade"
        )
        self.assertEqual(records.order_by("added").last().quantity, 4)

    def test_add_double(self):
        records = Record.objects.filter(
            item__user__username="john", item__name="lemonade"
        )
        self.assertEqual(records.count(), 4)

        data = {"quantity": "4", "unit": "301"}
        self.client.post("/item/lemonade/record/", data)
        self.client.post("/item/lemonade/record/", data)

        self.assertEqual(records.count(), 5)

    def test_add_after_minute(self):
        records = Record.objects.filter(
            item__user__username="john", item__name="lemonade"
        )
        self.assertEqual(records.count(), 4)

        data = {"quantity": "4", "unit": "301"}
        self.client.post("/item/lemonade/record/", data)

        latest = records.order_by("added").last()
        latest.added -= timedelta(minutes=1)
        latest.save()
        self.client.post("/item/lemonade/record/", data)

        self.assertEqual(records.count(), 6)

    def test_wrong_unit(self):
        data = {"quantity": "4", "unit": "1"}
        response = self.client.post("/item/lemonade/record/", data)

        self.assertFormError(
            response,
            "add_record",
            "unit",
            "Select a valid choice. That choice is not one of the available choices.",
        )


class UpdateTestCase(BaseTestCase):
    def setUp(self):
        self.client.login(username="john", password="password2")

    def test_update(self):
        latest = Record.objects.filter(item__user__username="john").order_by("added")
        data = {
            "not-exists": "3",
            "item-not-exists": "3",
            "item-butter": "5000",
            "item-lemonade": "4",
            "note": "update test",
        }
        response = self.client.post("/update/", data, follow=True)

        self.assertRedirects(response, "/")

        butter = latest.filter(item__name="butter").last()
        self.assertEqual(butter.quantity, 5)
        self.assertEqual(butter.note, "update test")

        lemonade = latest.filter(item__name="lemonade").last()
        self.assertEqual(lemonade.quantity, 4)
        self.assertEqual(lemonade.note, "update test")

    def test_update_double(self):
        rice = Record.objects.filter(item__user__username="john", item__name="rice")
        self.assertEqual(rice.count(), 0)

        self.client.post("/update/", {"item-rice": "5000"}, follow=True)
        self.client.post("/update/", {"item-rice": "5000"}, follow=True)

        self.assertEqual(rice.count(), 1)

    def test_update_after_minute(self):
        rice = Record.objects.filter(item__user__username="john", item__name="rice")
        self.assertEqual(rice.count(), 0)

        self.client.post("/update/", {"item-rice": "5000"}, follow=True)

        latest = rice.order_by("added").last()
        latest.added -= timedelta(minutes=1)
        latest.save()
        self.client.post("/update/", {"item-rice": "5000"}, follow=True)

        self.assertEqual(rice.count(), 2)


class DeleteItemTestCase(BaseTestCase):
    def setUp(self):
        self.client.login(username="john", password="password2")

    def test_delete_not_exists(self):
        response = self.client.post("/item/not-exists/delete/")
        self.assertEqual(response.status_code, 404)

    def test_delete(self):
        butter = Item.objects.filter(user__username="john", name="butter")
        self.assertTrue(butter.exists())

        response = self.client.post("/item/butter/delete/", follow=True)

        self.assertRedirects(response, "/")
        self.assertFalse(butter.exists())
