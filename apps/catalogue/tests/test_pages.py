from io import StringIO

from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.urls import reverse

from apps.catalogue.models import Product

from .base import CatalogueTestCase


class CataloguePageTests(CatalogueTestCase):
    def test_m2_tc_060_pages_require_login(self):
        """Page access | Anonymous GET catalogue pages | 302 redirect to /login/?next="""
        for name in ('page-products', 'page-product-add'):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertTrue(r['Location'].startswith('/login/?next='), name)

    def test_m2_tc_061_all_roles_can_open_pages(self):
        """Role access | Admin, Supervisor, Inspector open list, add, details, edit | 200 for every role"""
        product = Product.objects.create(name='Item')
        for user in (self.admin, self.supervisor, self.inspector):
            self.login_as(user)
            for name, args in (
                ('page-products', []),
                ('page-product-add', []),
                ('page-product-detail', [product.pk]),
                ('page-product-edit', [product.pk]),
            ):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, (user.role, name))

    def test_m2_tc_062_sidebar_link_is_live(self):
        """Navigation | Open dashboard as inspector | Product Catalogue link present and not marked 'coming soon'"""
        self.login_as(self.inspector)
        html = self.client.get(reverse('page-dashboard')).content.decode()
        self.assertIn('href="/products/"', html)
        self.assertNotIn('data-soon="Product Catalogue"', html)

    def test_m2_tc_063_static_assets_exist(self):
        """Assets | Resolve catalogue JS files | Found by staticfiles"""
        for path in ('catalogue/js/catalogue.js',):
            self.assertIsNotNone(finders.find(path), path)

    def test_m2_tc_064_seed_command_idempotent(self):
        """Demo data | Run seed_products twice | the 5 designed products, no duplicates"""
        call_command('seed_products', stdout=StringIO())
        call_command('seed_products', stdout=StringIO())
        self.assertEqual(Product.objects.count(), 5)
        self.assertTrue(all(len(p.gtin) == 13 for p in Product.objects.all()))
        self.assertEqual(
            set(Product.objects.values_list('category', flat=True)), {'Dairy', 'Snacks', 'Other'}
        )

    def test_m2_tc_065_no_scanner_and_six_field_form(self):
        """Design | Open list and add pages | no scanner route/link; entry form has only the 6 designed fields"""
        with self.assertRaises(Exception):
            reverse('page-product-scan')
        self.login_as(self.inspector)
        html = self.client.get(reverse('page-products')).content.decode()
        self.assertNotIn('Scan', html)
        self.assertIn('Manual Product Entry', html)
        for field in ('name', 'brand', 'gtin', 'net_quantity', 'category', 'manufacturer'):
            self.assertIn(f'name="{field}"', html)
        for gone in ('mrp', 'ingredients', 'allergens', 'fssai_license', 'country_of_origin', 'image_url'):
            self.assertNotIn(f'name="{gone}"', html)
        self.assertEqual(self.client.get(reverse('page-product-add')).status_code, 200)

    def test_m2_tc_066_edit_keeps_unchanged_demo_barcode(self):
        """Edit | Save a seeded product without touching its barcode | 200 (barcode not re-validated)"""
        call_command('seed_products', stdout=StringIO())
        self.login_as(self.admin)
        p = Product.objects.get(name='Tata Salt')
        r = self.client.put(f'/api/products/{p.pk}/', {'name': 'Tata Salt', 'gtin': p.gtin, 'category': 'Other'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
