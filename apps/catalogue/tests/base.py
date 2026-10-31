from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

User = get_user_model()
PASSWORD = 'Str0ng!Pass#2026'
EAN13 = '4006381333931'
UPC_A = '036000291452'
UPC_AS_EAN13 = '0036000291452'  # same product as UPC_A written as EAN-13
EAN8 = '96385074'
OFF_GET = 'apps.catalogue.services.open_food_facts.requests.get'


def fake_response(status=200, payload=None, bad_json=False):
    response = mock.Mock()
    response.status_code = status
    if bad_json:
        response.json.side_effect = ValueError('not json')
    else:
        response.json.return_value = payload
    return response


def off_payload(**overrides):
    product = {
        'product_name': 'Test Butter',
        'brands': 'Amul, Other',
        'categories': 'Dairy, Butters',
        'quantity': '500 g',
        'ingredients_text': 'Milk fat, salt',
        'allergens_tags': ['en:milk'],
        'manufacturing_places': 'Anand, India',
        'origins': 'India',
        'image_url': 'https://images.example.org/butter.jpg',
    }
    product.update(overrides)
    return {'status': 1, 'product': product}


class CatalogueTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin1', 'admin1@lip.test', PASSWORD, role='admin')
        cls.supervisor = User.objects.create_user('sup1', 'sup1@lip.test', PASSWORD, role='supervisor')
        cls.inspector = User.objects.create_user('insp1', 'insp1@lip.test', PASSWORD, role='inspector')

    def setUp(self):
        cache.clear()  # reset throttle counters

    def login_as(self, user):
        self.client.force_login(user)
