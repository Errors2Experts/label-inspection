from datetime import date, timedelta

from django.core.management import call_command
from django.urls import reverse

from apps.compliance import services
from apps.compliance.models import (
    ComplianceResult,
    ComplianceRule,
    PackStatus,
    RuleCategory,
    RulePack,
    Violation,
)

from .base import GOOD_LABEL, ComplianceTestCase

RULE_BODY = {
    'title': 'Brand must be declared',
    'category': None,
    'severity': 'minor',
    'regulation_ref': 'Test ref',
    'rule_type': 'required',
    'parameters': {'fields': ['brand']},
}


class SeedTests(ComplianceTestCase):
    def test_m4_tc_020_seed_is_complete_and_idempotent(self):
        """Seed | run seed_compliance twice | 26 rules, 6 categories, 3 packs (12 / 8 / 6 rules), no duplicates"""
        call_command('seed_compliance', verbosity=0)
        self.assertEqual(ComplianceRule.objects.count(), 26)
        self.assertEqual(RuleCategory.objects.count(), 6)
        basic = RulePack.objects.get(name='FSSAI Basic Label Pack')
        dairy = RulePack.objects.get(name='Dairy Specific Pack')
        imp = RulePack.objects.get(name='Import Goods Pack')
        self.assertEqual(
            [(p.version, p.items.count(), p.status) for p in (basic, dairy, imp)],
            [('v2.1', 12, 'active'), ('v1.3', 8, 'active'), ('v1.0', 6, 'draft')],
        )
        self.assertEqual((dairy.extends, imp.extends), (basic, basic))
        self.assertTrue(all(r.versions.count() == 1 for r in ComplianceRule.objects.all()))

    def test_m4_tc_021_only_rules_in_force(self):
        """Content | seeded rules | first two match the design; vegan 2022 rules present; nothing from the 2026 amendment"""
        r1, r2 = ComplianceRule.objects.get(code='R-001'), ComplianceRule.objects.get(code='R-002')
        self.assertEqual((r1.title, r1.severity, r1.category.name), ('FSSAI License Number must be present', 'critical', 'Mandatory Declarations'))
        self.assertEqual((r2.title, r2.severity, r2.category.name), ('MRP must be declared', 'critical', 'Mandatory Declarations'))
        self.assertTrue(ComplianceRule.objects.filter(category__name='Vegan Foods', regulation_ref__contains='Vegan Foods').exists())
        text = ' '.join(f'{r.title} {r.regulation_ref} {r.current_version.parameters}' for r in ComplianceRule.objects.all()).lower()
        for banned in ('amendment', '2027', 'fortified with', '100 cm'):
            self.assertNotIn(banned, text)
        self.assertFalse(RulePack.objects.filter(effective_from__gt=date(2026, 10, 29)).exists())


class PermissionTests(ComplianceTestCase):
    def test_m4_tc_030_rule_management_roles(self):
        """RBAC | Anonymous, Inspector, Supervisor, Admin call /api/rules/ | 403, 403, 200, 200"""
        url = reverse('rule-list')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login_as(self.inspector)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse('rule-pack-list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('rule-category-list')).status_code, 403)
        for user in (self.supervisor, self.admin):
            self.login_as(user)
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_m4_tc_031_inspector_cannot_write(self):
        """RBAC | Inspector POSTs rule / pack / category | 403 each"""
        self.login_as(self.inspector)
        cat = RuleCategory.objects.first()
        self.assertEqual(self.client.post(reverse('rule-list'), {**RULE_BODY, 'category': cat.pk}, format='json').status_code, 403)
        self.assertEqual(self.client.post(reverse('rule-pack-list'), {'name': 'X'}, format='json').status_code, 403)
        self.assertEqual(self.client.post(reverse('rule-category-list'), {'name': 'X'}, format='json').status_code, 403)


class RuleCrudTests(ComplianceTestCase):
    def setUp(self):
        self.login_as(self.supervisor)
        self.cat = RuleCategory.objects.get(name='Quantity & Price')

    def create(self, **over):
        body = {**RULE_BODY, 'category': self.cat.pk, **over}
        return self.client.post(reverse('rule-list'), body, format='json')

    def test_m4_tc_040_create_assigns_next_code_and_version_1(self):
        """Create rule | POST without code | R-027 assigned, version 1 created and current"""
        r = self.create()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['code'], 'R-027')
        rule = ComplianceRule.objects.get(code='R-027')
        self.assertEqual(rule.versions.count(), 1)
        self.assertTrue(rule.current_version.is_current)
        self.assertEqual(rule.created_by, self.supervisor)

    def test_m4_tc_041_validation(self):
        """Validation | bad type, bad field, bad regex, duplicate code, missing name | 400 with field errors"""
        self.assertEqual(self.create(rule_type='magic').status_code, 400)
        self.assertEqual(self.create(parameters={'fields': ['colour']}).status_code, 400)
        r = self.create(rule_type='regex', parameters={'fields': ['brand'], 'pattern': '('})
        self.assertEqual(r.status_code, 400)
        self.assertIn('parameters', r.data)
        self.assertEqual(self.create(code='R-001').status_code, 400)
        self.assertEqual(self.create(title='   ').status_code, 400)
        self.assertEqual(self.create(code='bad code!').status_code, 400)

    def test_m4_tc_042_editing_logic_appends_a_version(self):
        """Versioning | PUT changed parameters | version 2 current, version 1 untouched and still stored"""
        rule_id = self.create().data['id']
        url = reverse('rule-detail', args=[rule_id])
        body = self.client.get(url).data
        body['parameters'] = {'fields': ['brand', 'product_name']}
        body['change_note'] = 'Also name'
        r = self.client.put(url, body, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['version_number'], 2)
        rule = ComplianceRule.objects.get(pk=rule_id)
        v1, v2 = rule.versions.order_by('version_number')
        self.assertEqual(v1.parameters, {'fields': ['brand']})
        self.assertFalse(v1.is_current)
        self.assertTrue(v2.is_current)
        self.assertEqual(v2.change_note, 'Also name')
        hist = self.client.get(reverse('rule-versions', args=[rule_id]))
        self.assertEqual([v['version_number'] for v in hist.data], [2, 1])

    def test_m4_tc_043_metadata_edit_does_not_add_version(self):
        """Versioning | PATCH title/severity/is_active only | no new version"""
        rule_id = self.create().data['id']
        r = self.client.patch(reverse('rule-detail', args=[rule_id]), {'title': 'Brand declared', 'severity': 'major', 'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        rule = ComplianceRule.objects.get(pk=rule_id)
        self.assertEqual((rule.title, rule.severity, rule.is_active, rule.versions.count()), ('Brand declared', 'major', False, 1))

    def test_m4_tc_044_filters(self):
        """List | ?q ?category ?severity ?active ?pack | each narrows the list"""
        url = reverse('rule-list')
        self.assertEqual(self.client.get(url, {'q': 'R-010'}).data['count'], 1)
        self.assertEqual(self.client.get(url, {'q': 'licen'}).data['count'], 2)  # R-001, R-022
        self.assertEqual(self.client.get(url, {'severity': 'critical'}).data['count'], 10)
        dairy = RulePack.objects.get(name='Dairy Specific Pack')
        self.assertEqual(self.client.get(url, {'pack': dairy.pk}).data['count'], 8)  # the pack's own rules
        ComplianceRule.objects.filter(code='R-001').update(is_active=False)
        self.assertEqual(self.client.get(url, {'active': 'false'}).data['count'], 1)

    def test_m4_tc_045_delete_rules(self):
        """Delete | unused rule vs rule in a pack | 204 vs 409 and rule kept"""
        rule_id = self.create().data['id']
        self.assertEqual(self.client.delete(reverse('rule-detail', args=[rule_id])).status_code, 204)
        used = ComplianceRule.objects.get(code='R-001')
        r = self.client.delete(reverse('rule-detail', args=[used.pk]))
        self.assertEqual(r.status_code, 409)
        self.assertTrue(ComplianceRule.objects.filter(pk=used.pk).exists())

    def test_m4_tc_046_meta_and_summary(self):
        """Support endpoints | /meta/ and /summary/ | choices present; counts 26 / 3 / 6"""
        meta = self.client.get(reverse('rule-meta')).data
        self.assertIn('required', meta['rule_types'])
        self.assertIn('fssai_license', meta['data_fields'])
        s = self.client.get(reverse('rule-summary')).data
        self.assertEqual(s, {'active_rules': 26, 'rule_packs': 3, 'categories': 6})


class CategoryTests(ComplianceTestCase):
    def setUp(self):
        self.login_as(self.admin)

    def test_m4_tc_050_crud_and_protection(self):
        """Categories | create, duplicate name, rename, delete used / unused | 201, 400, 200, 409, 204"""
        r = self.client.post(reverse('rule-category-list'), {'name': 'Claims'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.post(reverse('rule-category-list'), {'name': 'claims'}, format='json').status_code, 400)
        url = reverse('rule-category-detail', args=[r.data['id']])
        self.assertEqual(self.client.patch(url, {'name': 'Claims & Marketing'}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)
        used = RuleCategory.objects.get(name='Date Marking')
        self.assertEqual(self.client.delete(reverse('rule-category-detail', args=[used.pk])).status_code, 409)


class PackTests(ComplianceTestCase):
    def setUp(self):
        self.login_as(self.admin)

    def test_m4_tc_060_pack_list_and_states(self):
        """Packs | list | design order: Basic v2.1 (12, active), Dairy v1.3 (8, active), Import v1.0 (6, draft)"""
        data = self.client.get(reverse('rule-pack-list')).data
        self.assertEqual(
            [(p['name'], p['version'], p['rule_count'], p['applies_to'], p['state']) for p in data],
            [
                ('FSSAI Basic Label Pack', 'v2.1', 12, 'All packaged food', 'active'),
                ('Dairy Specific Pack', 'v1.3', 8, 'Dairy products', 'active'),
                ('Import Goods Pack', 'v1.0', 6, 'Imported products', 'draft'),
            ],
        )
        self.assertNotIn('items', data[0])
        self.assertEqual(data[1]['extends_name'], 'FSSAI Basic Label Pack (v2.1)')

    def test_m4_tc_061_create_add_remove_refresh(self):
        """Packs | create empty pack, add rule, re-pin to older version, remove, refresh | items & versions correct"""
        r = self.client.post(reverse('rule-pack-list'), {'name': 'Beverage Pack', 'version': 'v0.1', 'product_categories': ['Beverages'], 'applies_to': 'Beverages'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.data['id']
        rule = ComplianceRule.objects.get(code='R-003')
        v1 = rule.versions.get(version_number=1)
        services.add_version(rule, {'rule_type': 'required', 'parameters': {'fields': ['product_name', 'brand']}}, self.admin, 'also brand')
        add = reverse('rule-pack-add-rule', args=[pid])
        r = self.client.post(add, {'rule': rule.pk, 'version': v1.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['items'][0]['version_number'], 1)
        self.assertEqual(r.data['items'][0]['latest_version'], 2)
        r = self.client.post(reverse('rule-pack-refresh', args=[pid]))
        self.assertEqual((r.data['refreshed'], r.data['items'][0]['version_number']), (1, 2))
        self.assertEqual(self.client.post(add, {'rule': 99999}, format='json').status_code, 400)
        other = ComplianceRule.objects.get(code='R-001')
        self.assertEqual(self.client.post(add, {'rule': other.pk, 'version': v1.pk}, format='json').status_code, 400)
        r = self.client.post(reverse('rule-pack-remove-rule', args=[pid]), {'rule': rule.pk}, format='json')
        self.assertEqual(r.data['items'], [])
        self.assertEqual(self.client.post(reverse('rule-pack-remove-rule', args=[pid]), {'rule': rule.pk}, format='json').status_code, 400)

    def test_m4_tc_064_extends_rules(self):
        """Packs | extends: self, chained, and a valid base | 400, 400, 200; pack serialises extends"""
        basic = RulePack.objects.get(name='FSSAI Basic Label Pack')
        dairy = RulePack.objects.get(name='Dairy Specific Pack')
        url = reverse('rule-pack-detail', args=[basic.pk])
        self.assertEqual(self.client.patch(url, {'extends': basic.pk}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'extends': dairy.pk}, format='json').status_code, 400)  # dairy already extends basic
        new = self.client.post(reverse('rule-pack-list'), {'name': 'Beverage Pack', 'extends': basic.pk}, format='json')
        self.assertEqual(new.status_code, 201, new.content)
        chained = self.client.post(reverse('rule-pack-list'), {'name': 'Sub Pack', 'extends': dairy.pk}, format='json')
        self.assertEqual(chained.status_code, 400)

    def test_m4_tc_062_pack_validation(self):
        """Packs | duplicate name, end before start | 400"""
        dup = RulePack.objects.first().name
        self.assertEqual(self.client.post(reverse('rule-pack-list'), {'name': dup.upper()}, format='json').status_code, 400)
        r = self.client.post(reverse('rule-pack-list'), {'name': 'P', 'effective_from': '2026-10-01', 'effective_to': '2026-09-01'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_m4_tc_063_used_pack_cannot_be_deleted(self):
        """Packs | delete a pack that has results vs one that has none | 409 vs 204"""
        basic = RulePack.objects.get(name='FSSAI Basic Label Pack')
        services.evaluate(GOOD_LABEL, basic, self.admin)
        self.assertEqual(self.client.delete(reverse('rule-pack-detail', args=[basic.pk])).status_code, 409)
        empty = RulePack.objects.create(name='Empty')
        self.assertEqual(self.client.delete(reverse('rule-pack-detail', args=[empty.pk])).status_code, 204)


class SelectionTests(ComplianceTestCase):
    def test_m4_tc_070_default_pack_by_date_and_category(self):
        """Pack selection | Dairy / other category / before 2022 / draft pack | Dairy pack, Basic, none, never the draft"""
        today = date(2026, 10, 29)
        self.assertEqual(services.select_pack('Dairy', today).name, 'Dairy Specific Pack')
        self.assertEqual(services.select_pack('Snacks', today).name, 'FSSAI Basic Label Pack')
        self.assertEqual(services.select_pack('', today).name, 'FSSAI Basic Label Pack')
        self.assertIsNone(services.select_pack('Dairy', date(2022, 1, 1)))  # L&D 2020 in force from 1 Jul 2022
        RulePack.objects.filter(name='Dairy Specific Pack').update(status=PackStatus.DRAFT)
        self.assertEqual(services.select_pack('Dairy', today).name, 'FSSAI Basic Label Pack')
        self.assertNotEqual(services.select_pack('Imported products', today).name, 'Import Goods Pack')


class EvaluateTests(ComplianceTestCase):
    url = property(lambda self: reverse('compliance-evaluate'))

    def post(self, data, **extra):
        return self.client.post(self.url, {'data': data, **extra}, format='json')

    def test_m4_tc_080_clean_label_has_no_violations(self):
        """Evaluate | complete, valid label (default pack) | 201, 0 violations, overall Requires Verification (physical-label checks)"""
        self.login_as(self.inspector)
        r = self.post(GOOD_LABEL, reference='TEST-1', reference_date='2026-10-29')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['non_compliant_count'], 0, [e for e in r.data['evaluations'] if e['outcome'] == 'non_compliant'])
        self.assertEqual(r.data['violations'], [])
        self.assertEqual(r.data['overall_status'], 'requires_verification')
        self.assertEqual((r.data['pack_name'], r.data['pack_version']), ('FSSAI Basic Label Pack', 'v2.1'))
        self.assertEqual(len(r.data['evaluations']), 12)
        outcomes = {e['rule_code']: e['outcome'] for e in r.data['evaluations']}
        self.assertEqual(outcomes['R-001'], 'compliant')
        self.assertEqual(outcomes['R-009'], 'requires_verification')  # veg symbol: physical check
        self.assertEqual(outcomes['R-012'], 'not_applicable')  # no vegan claim

    def test_m4_tc_081_violations_recorded(self):
        """Evaluate | missing licence, bad quantity, expiry in the past, no MRP | non-compliant; one Violation per failed rule"""
        self.login_as(self.inspector)
        bad = {**GOOD_LABEL, 'fssai_license': '', 'net_quantity': 'big pack', 'expiry_date': '01/01/2026', 'mrp': ''}
        r = self.post(bad, reference_date='2026-10-29')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['overall_status'], 'non_compliant')
        codes = {v['rule_code'] for v in r.data['violations']}
        self.assertEqual(codes, {'R-001', 'R-002', 'R-005', 'R-007'})
        self.assertEqual(r.data['non_compliant_count'], 4)
        result = ComplianceResult.objects.get(pk=r.data['id'])
        self.assertEqual(Violation.objects.filter(result=result).count(), 4)
        self.assertEqual(result.evaluated_by, self.inspector)
        v = next(v for v in r.data['violations'] if v['rule_code'] == 'R-001')
        self.assertEqual(v['message'], 'FSSAI licence / registration number is missing.')

    def test_m4_tc_082_dairy_pack_adds_its_rules_to_the_basic_ones(self):
        """Evaluate | category Dairy | Dairy pack chosen; 20 rules (8 own + 12 from Basic); sweetener rule fails then passes"""
        self.login_as(self.admin)
        data = {**GOOD_LABEL, 'ingredients': 'Milk, sugar, aspartame (INS 951)'}
        r = self.post(data, category='Dairy', reference_date='2026-10-29')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data['pack_name'], len(r.data['evaluations'])), ('Dairy Specific Pack', 20))
        outcomes = {e['rule_code']: e['outcome'] for e in r.data['evaluations']}
        self.assertEqual(outcomes['R-001'], 'compliant')  # a Basic rule, applied through "extends"
        self.assertEqual(outcomes['R-013'], 'compliant')  # "Contains milk" in GOOD_LABEL
        self.assertEqual(outcomes['R-018'], 'non_compliant')
        self.assertEqual(outcomes['R-019'], 'requires_verification')  # additives
        data['other_declarations'] += ' Contains artificial sweetener. Not recommended for children.'
        r = self.post(data, category='Dairy', reference_date='2026-10-29')
        outcomes = {e['rule_code']: e['outcome'] for e in r.data['evaluations']}
        self.assertEqual(outcomes['R-018'], 'compliant')

    def test_m4_tc_083_vegan_and_import_rules(self):
        """Evaluate | vegan claim; Import pack (draft: via service) | R-012 asks to verify; importer / licence / origin rules fire"""
        self.login_as(self.admin)
        vegan = {**GOOD_LABEL, 'product_name': 'Vegan Almond Spread'}
        r = self.post(vegan, reference_date='2026-10-29')
        outcomes = {e['rule_code']: e['outcome'] for e in r.data['evaluations']}
        self.assertEqual(outcomes['R-012'], 'requires_verification')
        draft = self.post(GOOD_LABEL, pack=RulePack.objects.get(name='Import Goods Pack').pk)
        self.assertEqual(draft.status_code, 400)  # draft packs are not used through the API
        imp = RulePack.objects.get(name='Import Goods Pack')
        res = services.evaluate({**GOOD_LABEL, 'importer': '', 'fssai_license': '1234'}, imp, self.admin, reference_date=date(2026, 10, 29))
        out = {e.rule_code: e.outcome for e in res.evaluations.all()}
        self.assertEqual((out['R-021'], out['R-022']), ('non_compliant', 'non_compliant'))
        self.assertEqual((out['R-023'], out['R-024']), ('requires_verification', 'requires_verification'))
        ok = {**GOOD_LABEL, 'importer': 'ACME Imports, Mumbai 400001',
              'other_declarations': 'Country of origin: Italy. Imported in 10/2026. Batch B1.'}
        out = {e.rule_code: e.outcome for e in services.evaluate(ok, imp, self.admin, reference_date=date(2026, 10, 29)).evaluations.all()}
        self.assertEqual([out[c] for c in ('R-021', 'R-022', 'R-023', 'R-024')], ['compliant'] * 4)

    def test_m4_tc_084_history_keeps_version_context(self):
        """Versioning | evaluate, then edit the rule | stored evaluation still points to the old version and old wording"""
        self.login_as(self.admin)
        r = self.post({**GOOD_LABEL, 'product_name': ''}, reference_date='2026-10-29')
        result_id = r.data['id']
        rule = ComplianceRule.objects.get(code='R-003')
        services.add_version(rule, {'rule_type': 'required', 'parameters': {'fields': ['brand']}, 'failure_message': 'new'}, self.admin, 'changed')
        stored = self.client.get(reverse('compliance-result-detail', args=[result_id])).data
        ev = next(e for e in stored['evaluations'] if e['rule_code'] == 'R-003')
        self.assertEqual((ev['version_number'], ev['outcome']), (1, 'non_compliant'))
        self.assertIn('Name of food', ev['detail'])

    def test_m4_tc_085_input_errors(self):
        """Evaluate | empty data, unknown field, draft pack, no pack applies, pack with no rules | 400 each"""
        self.login_as(self.admin)
        self.assertEqual(self.post({}).status_code, 400)
        self.assertEqual(self.post({'colour': 'red'}).status_code, 400)
        draft = RulePack.objects.create(name='Draft')
        self.assertEqual(self.post(GOOD_LABEL, pack=draft.pk).status_code, 400)
        draft.status = PackStatus.ACTIVE
        draft.save()
        self.assertEqual(self.post(GOOD_LABEL, pack=draft.pk).status_code, 400)  # no rules
        RulePack.objects.filter(status=PackStatus.ACTIVE).update(status=PackStatus.RETIRED)
        r = self.post(GOOD_LABEL)
        self.assertEqual(r.status_code, 400)
        self.assertIn('No active rule pack', r.data['detail'])

    def test_m4_tc_086_inactive_rules_skipped(self):
        """Evaluate | deactivate R-001 | rule not evaluated"""
        self.login_as(self.admin)
        ComplianceRule.objects.filter(code='R-001').update(is_active=False)
        r = self.post(GOOD_LABEL, reference_date='2026-10-29')
        self.assertEqual(len(r.data['evaluations']), 11)

    def test_m4_tc_087_requires_login(self):
        """Evaluate | anonymous | 403"""
        self.assertEqual(self.post(GOOD_LABEL).status_code, 403)


class ResultVisibilityTests(ComplianceTestCase):
    def test_m4_tc_090_inspector_sees_only_own(self):
        """Results & violations | two inspectors + supervisor list | inspector: own only; supervisor: all; other's detail 404"""
        v1 = RulePack.objects.get(name='FSSAI Basic Label Pack')
        bad = {**GOOD_LABEL, 'fssai_license': ''}
        mine = services.evaluate(bad, v1, self.inspector, reference_date=date(2026, 10, 29))
        theirs = services.evaluate(bad, v1, self.inspector2, reference_date=date(2026, 10, 29))
        self.login_as(self.inspector)
        res = self.client.get(reverse('compliance-result-list'))
        self.assertEqual([r['id'] for r in res.data['results']], [mine.pk])
        self.assertNotIn('evaluations', res.data['results'][0])
        self.assertEqual(self.client.get(reverse('compliance-result-detail', args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('compliance-violation-list')).data['count'], 1)
        self.login_as(self.supervisor)
        self.assertEqual(self.client.get(reverse('compliance-result-list')).data['count'], 2)
        self.assertEqual(self.client.get(reverse('compliance-violation-list'), {'rule': 'r-001'}).data['count'], 2)
        self.assertEqual(self.client.get(reverse('compliance-violation-list'), {'severity': 'minor'}).data['count'], 0)
        self.assertEqual(self.client.get(reverse('compliance-result-list'), {'status': 'compliant'}).data['count'], 0)

    def test_m4_tc_091_future_reference_date_is_default_today(self):
        """Results | evaluate without reference_date | stored reference_date is today"""
        v1 = RulePack.objects.get(name='FSSAI Basic Label Pack')
        r = services.evaluate(GOOD_LABEL, v1, self.admin)
        self.assertLessEqual(abs((r.reference_date - date.today()).days), 1)
        self.assertLess(timedelta(0), timedelta(days=1))
