from django.urls import reverse

from apps.compliance.models import ComplianceRule, RulePack

from .base import ComplianceTestCase

STAFF_PAGES = [
    ('page-rules', []), ('page-rule-add', []), ('page-rule-categories', []), ('page-pack-add', []),
    ('page-evaluate', []),
]


class CompliancePageTests(ComplianceTestCase):
    def pages(self):
        rule = ComplianceRule.objects.first()
        pack = RulePack.objects.first()
        return STAFF_PAGES + [
            ('page-rule-edit', [rule.pk]), ('page-rule-versions', [rule.pk]), ('page-pack-detail', [pack.pk]),
        ]

    def test_m4_tc_100_pages_require_login(self):
        """Page access | anonymous GET of every compliance page | 302 to /login/?next="""
        for name, args in self.pages() + [('page-results', []), ('page-violations', [])]:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 302, name)
            self.assertTrue(r['Location'].startswith('/login/?next='), name)

    def test_m4_tc_101_staff_pages_by_role(self):
        """Role access | management pages as Admin/Supervisor vs Inspector | 200 vs 403"""
        for user in (self.admin, self.supervisor):
            self.login_as(user)
            for name, args in self.pages():
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, (user.role, name))
        self.login_as(self.inspector)
        for name, args in self.pages():
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403, name)

    def test_m4_tc_102_result_pages_open_to_all_roles(self):
        """Role access | results list, violations, result detail | 200 for every role"""
        for user in (self.admin, self.supervisor, self.inspector):
            self.login_as(user)
            for name, args in (('page-results', []), ('page-violations', []), ('page-result-detail', [1])):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, (user.role, name))

    def test_m4_tc_103_sidebar_link_live_for_staff_only(self):
        """Navigation | Compliance Rules link | present and live for staff, absent for inspector"""
        self.login_as(self.supervisor)
        html = self.client.get(reverse('page-dashboard')).content.decode()
        self.assertIn('href="/rules/"', html)
        self.assertNotIn('data-soon="Compliance Rules"', html)
        self.login_as(self.inspector)
        self.assertNotIn('href="/rules/"', self.client.get(reverse('page-dashboard')).content.decode())

    def test_m4_tc_104_overview_matches_design(self):
        """Design | Compliance Rules overview | 3 stat cards, Rule Packs table with View, Rules table (ID, name, category, severity, status)"""
        self.login_as(self.admin)
        html = self.client.get(reverse('page-rules')).content.decode()
        for text in ('+ Add Rule', 'Active Rules', 'Rule Packs', 'Categories', 'Pack name', 'Applies to', 'Rule ID', 'Rule name', 'Severity'):
            self.assertIn(text, html)
        self.assertNotIn('class="tabs"', html)  # no extra tab bar on the designed screen
        self.assertNotIn('Search rule ID', html)  # no extra search/filter toolbar

    def test_m4_tc_105_rule_form_is_guided(self):
        """Usability | Add Rule page | plain-language check types, field tick-boxes and condition builder; JSON only behind Advanced"""
        self.login_as(self.admin)
        html = self.client.get(reverse('page-rule-add')).content.decode()
        for text in ('What should be checked?', 'When does this rule apply?', 'id="guided-box"', 'id="apply-mode"', 'Advanced: edit the settings as JSON'):
            self.assertIn(text, html)
        self.assertIn('id="advanced-box" hidden', html)  # JSON boxes are hidden until Advanced is ticked

