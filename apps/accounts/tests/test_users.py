from django.urls import reverse

from .base import PASSWORD, AccountsTestCase, User

NEW_USER = {
    'username': 'insp2',
    'email': 'insp2@lip.test',
    'password': 'Valid#Pass2026x',
    'role': 'inspector',
    'first_name': 'Ravi',
    'last_name': 'K',
    'employee_id': 'E002',
}


class UserManagementTests(AccountsTestCase):
    def test_m1_tc_030_admin_creates_inspector(self):
        self.login_as(self.admin)
        r = self.client.post(reverse('user-list'), NEW_USER)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn('password', r.data)
        created = User.objects.get(username='insp2')
        self.assertTrue(created.check_password(NEW_USER['password']))  # stored hashed
        self.assertNotEqual(created.password, NEW_USER['password'])

    def test_m1_tc_031_duplicate_username_rejected(self):
        self.login_as(self.admin)
        r = self.client.post(reverse('user-list'), {**NEW_USER, 'username': 'insp1'})
        self.assertEqual(r.status_code, 400)

    def test_m1_tc_031b_username_unique_ignoring_case(self):
        self.login_as(self.admin)
        r = self.client.post(reverse('user-list'), {**NEW_USER, 'username': 'INSP1'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('username', r.data)

    def test_m1_tc_032_duplicate_email_rejected_case_insensitive(self):
        self.login_as(self.admin)
        r = self.client.post(reverse('user-list'), {**NEW_USER, 'email': 'INSP1@lip.test'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('email', r.data)

    def test_m1_tc_033_mandatory_fields_enforced(self):
        self.login_as(self.admin)
        r = self.client.post(reverse('user-list'), {'username': 'x'})
        self.assertEqual(r.status_code, 400)
        for field in ('email', 'password'):
            self.assertIn(field, r.data)

    def test_m1_tc_034_weak_password_rejected(self):
        self.login_as(self.admin)
        for weak in ('short1', '12345678', 'password'):
            r = self.client.post(reverse('user-list'), {**NEW_USER, 'password': weak})
            self.assertEqual(r.status_code, 400, weak)
            self.assertIn('password', r.data)

    def test_m1_tc_035_admin_edits_user_and_role(self):
        self.login_as(self.admin)
        r = self.client.put(
            reverse('user-detail', args=[self.inspector.pk]),
            {
                'email': 'insp1@lip.test',
                'first_name': 'Updated',
                'last_name': 'Name',
                'role': 'supervisor',
                'phone': '9999999999',
                'is_active': True,
                'employee_id': 'E001',
            },
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.inspector.refresh_from_db()
        self.assertEqual((self.inspector.first_name, self.inspector.role), ('Updated', 'supervisor'))

    def test_m1_tc_036_delete_deactivates_not_removes(self):
        self.login_as(self.admin)
        r = self.client.delete(reverse('user-detail', args=[self.inspector.pk]))
        self.assertEqual(r.status_code, 200)
        self.inspector.refresh_from_db()
        self.assertFalse(self.inspector.is_active)
        self.assertTrue(User.objects.filter(pk=self.inspector.pk).exists())

    def test_m1_tc_037_deactivated_user_cannot_login_then_reactivate(self):
        self.login_as(self.admin)
        self.client.delete(reverse('user-detail', args=[self.inspector.pk]))
        self.client.logout()
        bad = self.client.post(reverse('auth-login'), {'identifier': 'insp1', 'password': PASSWORD})
        self.assertEqual(bad.status_code, 401)
        self.login_as(self.admin)
        self.assertEqual(self.client.post(reverse('user-activate', args=[self.inspector.pk])).status_code, 200)
        self.client.logout()
        ok = self.client.post(reverse('auth-login'), {'identifier': 'insp1', 'password': PASSWORD})
        self.assertEqual(ok.status_code, 200)

    def test_m1_tc_038_admin_cannot_deactivate_or_demote_self(self):
        self.login_as(self.admin)
        self.assertEqual(self.client.delete(reverse('user-detail', args=[self.admin.pk])).status_code, 400)
        r = self.client.patch(reverse('user-detail', args=[self.admin.pk]), {'role': 'inspector'})
        self.assertEqual(r.status_code, 400)

    def _usernames(self, response):
        data = response.data['results'] if isinstance(response.data, dict) else response.data
        return [u['username'] for u in data]

    def test_m1_tc_039_list_filters(self):
        self.login_as(self.admin)
        self.assertEqual(self._usernames(self.client.get(reverse('user-list'), {'role': 'inspector'})), ['insp1'])
        self.assertEqual(self._usernames(self.client.get(reverse('user-list'), {'q': 'E001'})), ['insp1'])
        self.assertEqual(self._usernames(self.client.get(reverse('user-list'), {'is_active': 'false'})), [])


class RoleEnforcementTests(AccountsTestCase):
    """Roles must restrict access to unauthorised functions (FDS 9.9)."""

    def test_m1_tc_040_inspector_denied_user_management(self):
        self.login_as(self.inspector)
        self.assertEqual(self.client.get(reverse('user-list')).status_code, 403)
        self.assertEqual(self.client.post(reverse('user-list'), NEW_USER).status_code, 403)
        self.assertEqual(self.client.get(reverse('roles')).status_code, 403)

    def test_m1_tc_041_supervisor_read_only_on_users(self):
        self.login_as(self.supervisor)
        self.assertEqual(self.client.get(reverse('user-list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('user-detail', args=[self.inspector.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('user-list'), NEW_USER).status_code, 403)
        self.assertEqual(self.client.delete(reverse('user-detail', args=[self.inspector.pk])).status_code, 403)
        self.assertEqual(
            self.client.patch(reverse('user-detail', args=[self.inspector.pk]), {'role': 'admin'}).status_code, 403
        )

    def test_m1_tc_042_roles_matrix_for_admin(self):
        self.login_as(self.admin)
        r = self.client.get(reverse('roles'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['roles']), 3)
        self.assertEqual(r.data['matrix']['User Management']['inspector'], 'no')

    def test_m1_tc_043_superuser_forced_to_admin_role(self):
        su = User.objects.create_superuser('root', 'root@lip.test', PASSWORD)
        self.assertEqual(su.role, 'admin')

    def test_m1_tc_044_permission_helpers_for_other_modules(self):
        from rest_framework.test import APIRequestFactory

        from apps.accounts.permissions import IsAdmin, IsAdminOrSupervisor, IsAnyRole

        req = APIRequestFactory().get('/')
        for user, expected in (
            (self.admin, (True, True, True)),
            (self.supervisor, (False, True, True)),
            (self.inspector, (False, False, True)),
        ):
            req.user = user
            got = tuple(p().has_permission(req, None) for p in (IsAdmin, IsAdminOrSupervisor, IsAnyRole))
            self.assertEqual(got, expected, user.username)
