from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

User = get_user_model()
PASSWORD = 'Str0ng!Pass#2026'


class AccountsTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin1', 'admin1@lip.test', PASSWORD, role='admin')
        cls.supervisor = User.objects.create_user('sup1', 'sup1@lip.test', PASSWORD, role='supervisor')
        cls.inspector = User.objects.create_user(
            'insp1', 'insp1@lip.test', PASSWORD, role='inspector', employee_id='E001'
        )

    def setUp(self):
        cache.clear()  # reset throttle counters between tests

    def login_as(self, user):
        self.client.force_login(user)
