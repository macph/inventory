"""
Tests for views.

"""
from django.contrib.auth import get_user_model
from django.test import TestCase


class BaseTestCase(TestCase):
    fixtures = ["units.json", "test_data.json"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # user passwords loaded from test data fixture are not hashed, set them properly
        user_class = get_user_model()
        all_users = user_class.objects.all()
        for user in all_users:
            user.set_password(user.password)
        user_class.objects.bulk_update(all_users, ("password",))


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
        self.assertEqual(response.redirect_chain, [])

    def test_try_api_logged_in(self):
        self.client.login(username="john", password="password2")
        response = self.client.get("/records", follow=True)
        self.assertEqual(response.status_code, 200)

    def test_logout(self):
        self.client.login(username="john", password="password2")
        self.client.logout()


class AddItemTestCase(BaseTestCase):
    pass


class GetItemTestCase(BaseTestCase):
    pass


class RecordsTestCase(BaseTestCase):
    pass


class EditItemTestCase(BaseTestCase):
    pass


class AddRecordTestCase(BaseTestCase):
    pass


class UpdateTestCase(BaseTestCase):
    pass


class DeleteItemTestCase(BaseTestCase):
    pass
