from django.contrib.staticfiles import finders
from django.urls import reverse

from .base import AccountsTestCase


class PageAccessTests(AccountsTestCase):
    def test_m1_tc_060_login_page_public_and_sets_csrf_cookie(self):
        r = self.client.get(reverse('page-login'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('csrftoken', r.cookies)
        self.assertContains(r, 'Sign in')

    def test_m1_tc_061_protected_pages_redirect_to_login_with_next(self):
        for name in ('page-dashboard', 'page-users', 'page-roles', 'page-profile'):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertTrue(r['Location'].startswith('/login/?next='), name)

    def test_m1_tc_062_logged_in_user_skips_login_page(self):
        self.login_as(self.inspector)
        self.assertRedirects(
            self.client.get(reverse('page-login')), reverse('page-dashboard'), fetch_redirect_response=False
        )

    def test_m1_tc_063_inspector_forbidden_on_admin_pages(self):
        self.login_as(self.inspector)
        for name in ('page-users', 'page-roles', 'page-user-add'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        self.assertEqual(self.client.get(reverse('page-user-detail', args=[1])).status_code, 403)

    def test_m1_tc_064_supervisor_read_only_pages(self):
        self.login_as(self.supervisor)
        self.assertEqual(self.client.get(reverse('page-users')).status_code, 200)
        self.assertEqual(self.client.get(reverse('page-roles')).status_code, 200)
        self.assertEqual(self.client.get(reverse('page-user-add')).status_code, 403)
        self.assertEqual(self.client.get(reverse('page-user-edit', args=[self.inspector.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('page-users')), '+ Add Inspector')

    def test_m1_tc_065_admin_can_open_all_m1_pages(self):
        self.login_as(self.admin)
        pages = [
            ('page-dashboard', []),
            ('page-users', []),
            ('page-user-add', []),
            ('page-roles', []),
            ('page-profile', []),
            ('page-user-detail', [self.inspector.pk]),
            ('page-user-edit', [self.inspector.pk]),
        ]
        for name, args in pages:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        self.assertContains(self.client.get(reverse('page-users')), '+ Add Inspector')

    def test_m1_tc_066_sidebar_menu_filtered_by_role(self):
        self.login_as(self.inspector)
        html = self.client.get(reverse('page-dashboard')).content.decode()
        self.assertIn('New Inspection', html)
        self.assertNotIn('Compliance Rules', html)
        self.assertNotIn('Roles &amp; Permissions', html)
        self.login_as(self.admin)
        html = self.client.get(reverse('page-dashboard')).content.decode()
        self.assertIn('Compliance Rules', html)
        self.assertIn('Roles &amp; Permissions', html)

    def test_m1_tc_067_home_redirects_to_dashboard(self):
        self.login_as(self.inspector)
        self.assertRedirects(self.client.get('/'), reverse('page-dashboard'), fetch_redirect_response=False)

    def test_m1_tc_068_static_assets_exist(self):
        for path in (
            'css/lip.css',
            'js/lip.js',
            'accounts/js/auth.js',
            'accounts/js/users.js',
            'accounts/js/account.js',
        ):
            self.assertIsNotNone(finders.find(path), path)

    def test_m1_tc_069_display_name_and_initials(self):
        self.inspector.first_name, self.inspector.last_name = 'Sathish', 'Vishnu'
        self.inspector.save()
        self.assertEqual((self.inspector.full_name, self.inspector.initials), ('Sathish Vishnu', 'SV'))
        self.assertEqual(self.supervisor.full_name, 'sup1')  # falls back to username
        self.assertEqual(self.supervisor.initials, 'SU')
        self.login_as(self.inspector)
        self.assertEqual(self.client.get(reverse('profile')).data['initials'], 'SV')
