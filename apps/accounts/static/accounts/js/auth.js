/* Login, forgot-password and reset-password pages. */
(function () {
  'use strict';
  const { $, api, showErrors, clearErrors, busy, safeNext } = LIP;

  function bind(id, handler) {
    const form = $(id);
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(form);
      const btn = $('button[type=submit]', form);
      busy(btn, true);
      try { await handler(form, Object.fromEntries(new FormData(form))); } catch (err) { showErrors(form, err); } finally { busy(btn, false); }
    });
  }

  bind('#login-form', async (form, v) => {
    if (!v.identifier.trim() || !v.password) throw { message: 'Please enter your username/email and password.' };
    await api('/api/auth/login/', { method: 'POST', body: { identifier: v.identifier, password: v.password }, auth: false });
    location.href = safeNext(new URLSearchParams(location.search).get('next'));
  });

  bind('#forgot-form', async (form, v) => {
    const data = await api('/api/auth/password-reset/', { method: 'POST', body: { email: v.email }, auth: false });
    const ok = $('#forgot-ok');
    ok.textContent = data.detail;
    ok.hidden = false;
  });

  bind('#reset-form', async (form, v) => {
    const q = new URLSearchParams(location.search);
    if (!q.get('uid') || !q.get('token')) throw { message: 'This password reset link is invalid or has expired.' };
    if (v.new_password !== v.confirm) throw { data: { confirm: ['Passwords do not match.'] } };
    await api('/api/auth/password-reset/confirm/', { method: 'POST', auth: false, body: { uid: q.get('uid'), token: q.get('token'), new_password: v.new_password } });
    LIP.toast('Password updated. Please sign in.', 'success');
    setTimeout(() => { location.href = '/login/'; }, 1200);
  });
})();
