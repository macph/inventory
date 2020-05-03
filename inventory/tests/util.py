"""
Test utilities.

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
