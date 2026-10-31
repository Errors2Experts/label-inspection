from unittest import mock

import requests
from django.conf import settings
from django.urls import reverse

from apps.catalogue.models import Product, ProductSource
from apps.catalogue.services.open_food_facts import map_product

from .base import EAN8, EAN13, OFF_GET, UPC_A, UPC_AS_EAN13, CatalogueTestCase, fake_response, off_payload

NEW = {'name': 'Parle-G Biscuits', 'gtin': EAN13, 'brand': 'Parle', 'category': 'Biscuits', 'mrp': '10.00'}


def results(response):
    return response.data['results'] if isinstance(response.data, dict) else response.data


class CatalogueListTests(CatalogueTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Product.objects.create(name='Amul Butter 500g', brand='Amul', category='Dairy', gtin=EAN13)
        Product.objects.create(
            name='Maggi Noodles',
            brand='Nestle',
            category='Instant food',
            gtin=UPC_A,
            source=ProductSource.OPEN_FOOD_FACTS,
        )

    def test_m2_tc_010_login_required(self):
        """Authentication | Anonymous GET /api/products/ | 401/403"""
        self.assertIn(self.client.get(reverse('product-list')).status_code, (401, 403))

    def test_m2_tc_011_all_roles_can_read(self):
        """Read access | Admin, Supervisor, Inspector GET list and detail | 200 for each"""
        pk = Product.objects.first().pk
        for user in (self.admin, self.supervisor, self.inspector):
            self.login_as(user)
            self.assertEqual(self.client.get(reverse('product-list')).status_code, 200, user.role)
            self.assertEqual(self.client.get(reverse('product-detail', args=[pk])).status_code, 200, user.role)

    def test_m2_tc_012_search_by_name_brand_barcode(self):
        """Search | ?q=butter, ?q=nestle, ?q=<partial barcode> | Only matching products"""
        self.login_as(self.inspector)
        names = lambda q: [p['name'] for p in results(self.client.get(reverse('product-list'), {'q': q}))]  # noqa: E731
        self.assertEqual(names('butter'), ['Amul Butter 500g'])
        self.assertEqual(names('nestle'), ['Maggi Noodles'])
        self.assertEqual(names('381333'), ['Amul Butter 500g'])
        self.assertEqual(names('nothing-here'), [])

    def test_m2_tc_013_search_input_sanitised(self):
        """Search sanitising | Control chars, 5000-char string, SQL-looking text | 200, no error, no leak"""
        self.login_as(self.inspector)
        for q in ("x\x00\x1f'; DROP TABLE catalogue_product;--", 'a' * 5000, '%_%'):
            self.assertEqual(self.client.get(reverse('product-list'), {'q': q}).status_code, 200)
        self.assertEqual(Product.objects.count(), 2)

    def test_m2_tc_014_filters(self):
        """Filters | ?source=open_food_facts, ?category=dairy, bogus source | Filtered; bogus ignored"""
        self.login_as(self.inspector)
        url = reverse('product-list')
        self.assertEqual(len(results(self.client.get(url, {'source': 'open_food_facts'}))), 1)
        self.assertEqual(len(results(self.client.get(url, {'category': 'dairy'}))), 1)
        self.assertEqual(len(results(self.client.get(url, {'source': 'bogus'}))), 2)

    def test_m2_tc_015_paginated_shape(self):
        """Pagination | GET list | Response has count, next, previous, results"""
        self.login_as(self.inspector)
        data = self.client.get(reverse('product-list')).data
        self.assertEqual(set(data), {'count', 'next', 'previous', 'results'})
        self.assertEqual(data['count'], 2)


class CatalogueWriteTests(CatalogueTestCase):
    def test_m2_tc_020_create_manual_product(self):
        """Manual entry | Inspector POST valid product with spaced barcode | 201; source=manual; barcode normalised"""
        self.login_as(self.inspector)
        r = self.client.post(reverse('product-list'), {**NEW, 'gtin': '4006 381 333931'})
        self.assertEqual(r.status_code, 201, r.data)
        product = Product.objects.get(pk=r.data['id'])
        self.assertEqual((product.gtin, product.source, product.created_by), (EAN13, 'manual', self.inspector))

    def test_m2_tc_021_barcode_optional(self):
        """Product without barcode | POST name only; then a second one | Both 201 (NULL barcodes do not clash)"""
        self.login_as(self.inspector)
        for name in ('Loose item A', 'Loose item B'):
            self.assertEqual(self.client.post(reverse('product-list'), {'name': name}).status_code, 201)

    def test_m2_tc_022_name_required(self):
        """Mandatory field | POST without name / blank name | 400 on name"""
        self.login_as(self.inspector)
        self.assertIn('name', self.client.post(reverse('product-list'), {'gtin': EAN13}).data)
        self.assertEqual(self.client.post(reverse('product-list'), {'name': '   '}).status_code, 400)

    def test_m2_tc_023_invalid_barcode_rejected(self):
        """Barcode validation | Bad check digit, wrong length | 400 on gtin"""
        self.login_as(self.inspector)
        for bad in ('4006381333932', '12345'):
            r = self.client.post(reverse('product-list'), {**NEW, 'gtin': bad})
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn('gtin', r.data)

    def test_m2_tc_024_duplicate_barcode_rejected_across_upc_ean(self):
        """Duplicate barcode | Create UPC-A, then the same code as EAN-13 | 400 'already exists'"""
        self.login_as(self.inspector)
        self.assertEqual(self.client.post(reverse('product-list'), {'name': 'A', 'gtin': UPC_A}).status_code, 201)
        r = self.client.post(reverse('product-list'), {'name': 'B', 'gtin': UPC_AS_EAN13})
        self.assertEqual(r.status_code, 400)
        self.assertIn('already exists', str(r.data['gtin']))

    def test_m2_tc_025_negative_mrp_rejected(self):
        """MRP validation | mrp = -5 | 400 on mrp"""
        self.login_as(self.inspector)
        self.assertIn('mrp', self.client.post(reverse('product-list'), {**NEW, 'mrp': '-5'}).data)

    def test_m2_tc_026_unsafe_image_url_rejected(self):
        """Image URL safety | image_url = javascript:alert(1) | 400 on image_url"""
        self.login_as(self.inspector)
        r = self.client.post(reverse('product-list'), {**NEW, 'image_url': 'javascript:alert(1)'})
        self.assertIn('image_url', r.data)

    def test_m2_tc_027_put_updates_product(self):
        """Edit | PUT new name/MRP on a product | 200; saved; updated_by set; source unchanged"""
        product = Product.objects.create(name='Old', gtin=EAN13, source=ProductSource.OPEN_FOOD_FACTS)
        self.login_as(self.supervisor)
        r = self.client.put(
            reverse('product-detail', args=[product.pk]), {'name': 'New name', 'gtin': EAN13, 'mrp': '99.50'}
        )
        self.assertEqual(r.status_code, 200, r.data)
        product.refresh_from_db()
        self.assertEqual((product.name, str(product.mrp), product.updated_by), ('New name', '99.50', self.supervisor))
        self.assertEqual(product.source, ProductSource.OPEN_FOOD_FACTS)

    def test_m2_tc_028_update_cannot_steal_another_barcode(self):
        """Duplicate on edit | Change product B's barcode to product A's | 400"""
        Product.objects.create(name='A', gtin=EAN13)
        b = Product.objects.create(name='B', gtin=EAN8)
        self.login_as(self.admin)
        r = self.client.patch(reverse('product-detail', args=[b.pk]), {'gtin': EAN13})
        self.assertEqual(r.status_code, 400)

    def test_m2_tc_029_delete_not_available(self):
        """No delete | DELETE /api/products/{id}/ | 405 (history must keep valid product links)"""
        product = Product.objects.create(name='A')
        self.login_as(self.admin)
        self.assertEqual(self.client.delete(reverse('product-detail', args=[product.pk])).status_code, 405)

    def test_m2_tc_030_protected_fields_ignored(self):
        """Read-only fields | POST with source and created_by in payload | Ignored; server values used"""
        self.login_as(self.inspector)
        r = self.client.post(reverse('product-list'), {**NEW, 'source': 'open_food_facts', 'created_by': self.admin.pk})
        self.assertEqual(r.status_code, 201)
        product = Product.objects.get(pk=r.data['id'])
        self.assertEqual((product.source, product.created_by), ('manual', self.inspector))


class LookupTests(CatalogueTestCase):
    url = property(lambda self: reverse('product-lookup'))

    def test_m2_tc_040_local_hit_skips_external(self):
        """Local lookup | GET lookup?gtin= for a catalogued barcode | found, source=local, no external call"""
        Product.objects.create(name='Local item', gtin=EAN13)
        self.login_as(self.inspector)
        with mock.patch(OFF_GET) as get:
            r = self.client.get(self.url, {'gtin': EAN13})
        self.assertEqual((r.status_code, r.data['found'], r.data['source']), (200, True, 'local'))
        self.assertEqual(r.data['product']['name'], 'Local item')
        get.assert_not_called()

    def test_m2_tc_041_upc_and_ean_forms_match(self):
        """UPC/EAN equivalence | Catalogue holds UPC-A; look up its EAN-13 form | Found locally"""
        Product.objects.create(name='US item', gtin=UPC_A)
        self.login_as(self.inspector)
        with mock.patch(OFF_GET) as get:
            r = self.client.get(self.url, {'gtin': UPC_AS_EAN13})
        self.assertTrue(r.data['found'])
        get.assert_not_called()

    def test_m2_tc_042_malformed_barcode_400(self):
        """Malformed barcode | gtin missing / bad check digit / letters | 400 with message"""
        self.login_as(self.inspector)
        for bad in ({}, {'gtin': '4006381333932'}, {'gtin': 'abc'}):
            r = self.client.get(self.url, bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn('gtin', r.data)

    def test_m2_tc_043_external_hit_is_cached(self):
        """External lookup | Unknown locally, API returns product; look up twice | Fetched, saved; 2nd call is local"""
        self.login_as(self.inspector)
        with mock.patch(OFF_GET, return_value=fake_response(payload=off_payload())) as get:
            first = self.client.get(self.url, {'gtin': EAN13})
            second = self.client.get(self.url, {'gtin': EAN13})
        self.assertEqual((first.data['found'], first.data['source']), (True, 'open_food_facts'))
        self.assertEqual(second.data['source'], 'local')
        self.assertEqual(get.call_count, 1)
        saved = Product.objects.get(gtin=EAN13)
        self.assertEqual(
            (saved.name, saved.brand, saved.allergens, saved.source), ('Test Butter', 'Amul', 'milk', 'open_food_facts')
        )
        self.assertEqual(saved.created_by, self.inspector)

    def test_m2_tc_044_unknown_everywhere(self):
        """Unknown product | API returns status 0 and HTTP 404 | found=false, not_found, can_continue=true, 200"""
        self.login_as(self.inspector)
        for resp in (fake_response(404, {'status': 0}), fake_response(200, {'status': 0})):
            with mock.patch(OFF_GET, return_value=resp):
                r = self.client.get(self.url, {'gtin': EAN13})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(
                (r.data['found'], r.data['external_status'], r.data['can_continue']), (False, 'not_found', True)
            )
        self.assertEqual(Product.objects.count(), 0)

    def test_m2_tc_045_external_timeout_does_not_block(self):
        """API timeout | requests raises Timeout | 200 found=false, external_status=unavailable, manual-entry message"""
        self.login_as(self.inspector)
        with mock.patch(OFF_GET, side_effect=requests.exceptions.Timeout):
            r = self.client.get(self.url, {'gtin': EAN13})
        self.assertEqual((r.status_code, r.data['found'], r.data['external_status']), (200, False, 'unavailable'))
        self.assertIn('manually', r.data['detail'])

    def test_m2_tc_046_external_server_error_does_not_block(self):
        """API HTTP 500 | Product service errors | Same graceful 'unavailable' result"""
        self.login_as(self.inspector)
        with mock.patch(OFF_GET, return_value=fake_response(500, {})):
            r = self.client.get(self.url, {'gtin': EAN13})
        self.assertEqual((r.status_code, r.data['external_status']), (200, 'unavailable'))

    def test_m2_tc_047_external_invalid_json_does_not_block(self):
        """API garbage | 200 response that is not JSON | Graceful 'unavailable' result"""
        self.login_as(self.inspector)
        with mock.patch(OFF_GET, return_value=fake_response(bad_json=True)):
            r = self.client.get(self.url, {'gtin': EAN13})
        self.assertEqual(r.data['external_status'], 'unavailable')

    def test_m2_tc_048_external_mapping(self):
        """Field mapping | Payload with tags, multiple brands, http image, no name | Clean Product fields"""
        mapped = map_product(off_payload(image_url='ftp://x/y.jpg')['product'], EAN13)
        self.assertEqual(
            (mapped['brand'], mapped['category'], mapped['allergens'], mapped['image_url']),
            ('Amul', 'Dairy', 'milk', ''),
        )
        self.assertEqual(map_product({}, EAN8)['name'], f'Unnamed product {EAN8}')
        long = map_product({'product_name': 'x' * 400}, EAN13)
        self.assertEqual(len(long['name']), 255)

    def test_m2_tc_049_lookup_requires_login(self):
        """Authentication | Anonymous GET lookup | 401/403"""
        self.assertIn(self.client.get(self.url, {'gtin': EAN13}).status_code, (401, 403))

    def test_m2_tc_050_lookup_rate_limited(self):
        """Rate limit | 61 lookups in a minute | 61st returns 429"""
        self.login_as(self.inspector)
        codes = [self.client.get(self.url, {'gtin': 'bad'}).status_code for _ in range(61)]
        self.assertEqual(codes[59], 400)
        self.assertEqual(codes[60], 429)

    def test_m2_tc_051_external_call_uses_timeout_and_user_agent(self):
        """Outbound call | Unknown barcode lookup | requests.get called with configured timeout and User-Agent"""
        self.login_as(self.inspector)
        with mock.patch(OFF_GET, return_value=fake_response(404, {'status': 0})) as get:
            self.client.get(self.url, {'gtin': EAN13})
        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs['timeout'], settings.PRODUCT_API_TIMEOUT)
        self.assertIn('User-Agent', kwargs['headers'])
        self.assertTrue(get.call_args.args[0].endswith(f'/product/{EAN13}.json'))


class CategoryListTests(CatalogueTestCase):
    def test_m2_tc_090_distinct_categories_for_filter(self):
        """Category filter | GET /api/products/categories/ | sorted distinct non-empty categories; needs login"""
        from apps.catalogue.models import Product

        Product.objects.create(name='A', category='Dairy')
        Product.objects.create(name='B', category='Dairy')
        Product.objects.create(name='C', category='Biscuits')
        Product.objects.create(name='D', category='')
        self.assertEqual(self.client.get('/api/products/categories/').status_code, 403)
        self.login_as(self.inspector)
        self.assertEqual(self.client.get('/api/products/categories/').json(), ['Biscuits', 'Dairy'])
