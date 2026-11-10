import re

from django.core import mail
from django.urls import reverse

from .base import PASSWORD, AccountsTestCase, User


class LoginTests(AccountsTestCase):
    def test_m1_tc_001_login_with_username(self):
        r = self.client.post(reverse('auth-login'), {'identifier': 'insp1', 'password': PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['user']['role'], 'inspector')
        self.assertIn('sessionid', r.cookies)

    def test_m1_tc_002_login_with_email_case_insensitive(self):
        r = self.client.post(reverse('auth-login'), {'identifier': 'INSP1@lip.test', 'password': PASSWORD})
        self.assertEqual(r.status_code, 200)

    def test_m1_tc_003_wrong_password_denied(self):
        r = self.client.post(reverse('auth-login'), {'identifier': 'insp1', 'password': 'nope'})
        self.assertEqual(r.status_code, 401)

    def test_m1_tc_004_error_does_not_leak_account_existence(self):
        bad_pw = self.client.post(reverse('auth-login'), {'identifier': 'insp1', 'password': 'nope'})
        no_user = self.client.post(reverse('auth-login'), {'identifier': 'ghost', 'password': 'nope'})
        self.assertEqual(bad_pw.data, no_user.data)
        self.assertEqual(bad_pw.status_code, no_user.status_code)

    def test_m1_tc_005_inactive_user_denied(self):
        User.objects.filter(pk=self.inspector.pk).update(is_active=False)
        r = self.client.post(reverse('auth-login'), {'identifier': 'insp1', 'password': PASSWORD})
        self.assertEqual(r.status_code, 401)

    def test_m1_tc_006_missing_fields_rejected(self):
        r = self.client.post(reverse('auth-login'), {'identifier': 'insp1'})
        self.assertEqual(r.status_code, 400)

    def test_m1_tc_007_logout_ends_session(self):
        self.client.post(reverse('auth-login'), {'identifier': 'insp1', 'password': PASSWORD})
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)
        self.assertEqual(self.client.post(reverse('auth-logout')).status_code, 200)
        self.assertIn(self.client.get(reverse('profile')).status_code, (401, 403))

    def test_m1_tc_008_protected_endpoint_requires_login(self):
        self.assertIn(self.client.get(reverse('user-list')).status_code, (401, 403))

    def test_m1_tc_009_csrf_enforced_on_login(self):
        from rest_framework.test import APIClient

        strict = APIClient(enforce_csrf_checks=True)
        r = strict.post(reverse('auth-login'), {'identifier': 'insp1', 'password': PASSWORD})
        self.assertEqual(r.status_code, 403)


class ThrottleTests(AccountsTestCase):
    def test_m1_tc_010_login_rate_limited(self):
        url = reverse('auth-login')
        codes = [self.client.post(url, {'identifier': 'insp1', 'password': 'bad'}).status_code for _ in range(11)]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10], 429)

    def test_m1_tc_011_password_reset_rate_limited(self):
        url = reverse('auth-password-reset')
        codes = [self.client.post(url, {'email': 'insp1@lip.test'}).status_code for _ in range(6)]
        self.assertEqual(codes[5], 429)


class PasswordResetTests(AccountsTestCase):
    def _request_reset(self, email):
        return self.client.post(reverse('auth-password-reset'), {'email': email})

    def _extract_link_params(self):
        body = mail.outbox[-1].body
        return re.search(r'uid=([^&\s]+)&token=([^\s]+)', body).groups()

    def test_m1_tc_020_reset_email_sent_for_known_user(self):
        r = self._request_reset('insp1@lip.test')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_m1_tc_021_unknown_email_same_response_no_email(self):
        known = self._request_reset('insp1@lip.test')
        unknown = self._request_reset('nobody@lip.test')
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)  # only the known one

    def test_m1_tc_022_reset_end_to_end(self):
        self._request_reset('insp1@lip.test')
        uid, token = self._extract_link_params()
        new_pw = 'Brand#New9Password'
        r = self.client.post(
            reverse('auth-password-reset-confirm'), {'uid': uid, 'token': token, 'new_password': new_pw}
        )
        self.assertEqual(r.status_code, 200)
        ok = self.client.post(reverse('auth-login'), {'identifier': 'insp1', 'password': new_pw})
        self.assertEqual(ok.status_code, 200)

    def test_m1_tc_023_token_cannot_be_reused(self):
        self._request_reset('insp1@lip.test')
        uid, token = self._extract_link_params()
        payload = {'uid': uid, 'token': token, 'new_password': 'Brand#New9Password'}
        self.assertEqual(self.client.post(reverse('auth-password-reset-confirm'), payload).status_code, 200)
        payload['new_password'] = 'Another#New8Password'
        self.assertEqual(self.client.post(reverse('auth-password-reset-confirm'), payload).status_code, 400)

    def test_m1_tc_024_invalid_token_rejected(self):
        self._request_reset('insp1@lip.test')
        uid, _ = self._extract_link_params()
        r = self.client.post(
            reverse('auth-password-reset-confirm'),
            {'uid': uid, 'token': 'bad-token', 'new_password': 'Brand#New9Password'},
        )
        self.assertEqual(r.status_code, 400)

    def test_m1_tc_025_weak_password_rejected_on_reset(self):
        self._request_reset('insp1@lip.test')
        uid, token = self._extract_link_params()
        r = self.client.post(
            reverse('auth-password-reset-confirm'), {'uid': uid, 'token': token, 'new_password': '12345678'}
        )
        self.assertEqual(r.status_code, 400)

    def test_m1_tc_026_inactive_user_gets_no_reset_email(self):
        User.objects.filter(pk=self.inspector.pk).update(is_active=False)
        self._request_reset('insp1@lip.test')
        self.assertEqual(len(mail.outbox), 0)
