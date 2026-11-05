from django.urls import reverse

from .base import PASSWORD, AccountsTestCase


class ProfileTests(AccountsTestCase):
    def test_m1_tc_050_view_own_profile(self):
        self.login_as(self.inspector)
        r = self.client.get(reverse('profile'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['username'], 'insp1')

    def test_m1_tc_051_update_own_profile(self):
        self.login_as(self.inspector)
        r = self.client.put(
            reverse('profile'), {'email': 'new@lip.test', 'first_name': 'Asha', 'last_name': 'M', 'phone': '9876543210'}
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.inspector.refresh_from_db()
        self.assertEqual(self.inspector.email, 'new@lip.test')

    def test_m1_tc_052_cannot_escalate_role_via_profile(self):
        self.login_as(self.inspector)
        self.client.patch(reverse('profile'), {'role': 'admin', 'username': 'hacker', 'employee_id': 'X'})
        self.inspector.refresh_from_db()
        self.assertEqual((self.inspector.role, self.inspector.username), ('inspector', 'insp1'))

    def test_m1_tc_053_profile_email_must_be_unique(self):
        self.login_as(self.inspector)
        r = self.client.patch(reverse('profile'), {'email': 'admin1@lip.test'})
        self.assertEqual(r.status_code, 400)

    def test_m1_tc_054_change_password(self):
        self.login_as(self.inspector)
        r = self.client.post(
            reverse('profile-change-password'), {'old_password': PASSWORD, 'new_password': 'Changed#Pass77'}
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)  # session kept
        self.inspector.refresh_from_db()
        self.assertTrue(self.inspector.check_password('Changed#Pass77'))

    def test_m1_tc_055_change_password_wrong_old(self):
        self.login_as(self.inspector)
        r = self.client.post(
            reverse('profile-change-password'), {'old_password': 'wrong', 'new_password': 'Changed#Pass77'}
        )
        self.assertEqual(r.status_code, 400)

    def test_m1_tc_056_change_password_weak_new(self):
        self.login_as(self.inspector)
        r = self.client.post(reverse('profile-change-password'), {'old_password': PASSWORD, 'new_password': '12345678'})
        self.assertEqual(r.status_code, 400)

    def test_m1_tc_057_profile_requires_login(self):
        self.assertIn(self.client.get(reverse('profile')).status_code, (401, 403))
