from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APITestCase

User = get_user_model()
PASSWORD = 'Str0ng!Pass#2026'

GOOD_LABEL = {
    'product_name': 'Salted Butter',
    'brand': 'Demo',
    'mrp': '270.00',
    'net_quantity': '500 g',
    'manufacturing_date': '01/09/2026',
    'expiry_date': '01/03/2027',
    'ingredients': 'Milk fat, common salt',
    'fssai_license': '10012345678901',
    'manufacturer': 'Demo Dairy Pvt Ltd, Anand, Gujarat 388001',
    'other_declarations': 'Contains milk. Batch No. B123. Consumer care: 1800-000-000. Veg.',
}


class ComplianceTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin1', 'admin1@lip.test', PASSWORD, role='admin')
        cls.supervisor = User.objects.create_user('sup1', 'sup1@lip.test', PASSWORD, role='supervisor')
        cls.inspector = User.objects.create_user('insp1', 'insp1@lip.test', PASSWORD, role='inspector')
        cls.inspector2 = User.objects.create_user('insp2', 'insp2@lip.test', PASSWORD, role='inspector')
        call_command('seed_compliance', verbosity=0)

    def login_as(self, user):
        self.client.force_login(user)
