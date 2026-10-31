/* LabelInspect shared front-end helpers: API client, toasts, dialogs, layout behaviour. */
(function () {
  'use strict';
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const cookie = (name) => (document.cookie.split('; ').find((r) => r.startsWith(name + '=')) || '').split('=')[1] || '';

  /** Turn a DRF error payload into one readable sentence. */
  function messageFrom(data) {
    if (!data) return 'Something went wrong. Please try again.';
    if (typeof data === 'string') return data;
    if (data.detail) return data.detail;
    const first = Object.values(data)[0];
    return Array.isArray(first) ? first[0] : String(first);
  }

  class ApiError extends Error {
    constructor(status, data) { super(messageFrom(data)); this.status = status; this.data = data; }
  }

  /** fetch wrapper: JSON in/out, CSRF header, redirect to login when the session has ended. */
  async function api(url, { method = 'GET', body, auth = true } = {}) {
    const res = await fetch(url, {
      method, credentials: 'same-origin',
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}), 'X-CSRFToken': cookie('csrftoken') },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch (_) { /* empty body */ }
    if (!res.ok) {
      const sessionEnded = res.status === 401 || (res.status === 403 && /credentials were not provided/i.test((data && data.detail) || ''));
      if (auth && sessionEnded) { location.href = '/login/?next=' + encodeURIComponent(location.pathname); return new Promise(() => {}); }
      throw new ApiError(res.status, data);
    }
    return data;
  }

  function toast(message, kind = '') {
    const el = Object.assign(document.createElement('div'), { className: 'toast ' + kind, textContent: message });
    $('#toasts').appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  function confirmDialog({ title, message, confirmText = 'Confirm', danger = false }) {
    return new Promise((resolve) => {
      const back = document.createElement('div');
      back.className = 'modal-back';
      back.innerHTML = `<div class="modal" role="dialog" aria-modal="true"><h3>${esc(title)}</h3><p>${esc(message)}</p>
        <div class="btns"><button class="btn secondary" data-no>Cancel</button>
        <button class="btn ${danger ? 'danger' : ''}" data-yes>${esc(confirmText)}</button></div></div>`;
      const done = (v) => { back.remove(); resolve(v); };
      back.addEventListener('click', (e) => { if (e.target === back || e.target.hasAttribute('data-no')) done(false); if (e.target.hasAttribute('data-yes')) done(true); });
      document.body.appendChild(back);
      $('[data-yes]', back).focus();
    });
  }

  /** Show server-side validation errors next to the matching inputs, or in the form banner. */
  function showErrors(form, err) {
    clearErrors(form);
    const data = err && err.data;
    let banner = '';
    if (data && typeof data === 'object' && !data.detail) {
      Object.entries(data).forEach(([field, msgs]) => {
        const input = form.elements[field];
        const text = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
        if (!input) { banner = banner || text; return; }
        input.classList.add('invalid');
        const small = Object.assign(document.createElement('div'), { className: 'field-error', textContent: text });
        input.closest('.field').appendChild(small);
      });
    } else {
      banner = (err && err.message) || 'Something went wrong.';
    }
    const box = $('.alert.error', form);
    if (box) { box.textContent = banner; box.hidden = !banner; }
  }
  function clearErrors(form) {
    $$('.field-error', form).forEach((n) => n.remove());
    $$('.invalid', form).forEach((n) => n.classList.remove('invalid'));
    const box = $('.alert.error', form);
    if (box) box.hidden = true;
  }
  function busy(btn, on, label) {
    if (!btn) return;
    if (on) { btn.dataset.label = btn.textContent; btn.textContent = label || 'Please wait...'; } else { btn.textContent = btn.dataset.label || btn.textContent; }
    btn.disabled = on;
  }

  const ROLE_PILL = { admin: 'teal', supervisor: 'amber', inspector: 'gray' };
  const roleLabel = (r) => ({ admin: 'Admin', supervisor: 'Supervisor', inspector: 'Inspector' }[r] || r);
  const rolePill = (r) => `<span class="pill ${ROLE_PILL[r] || 'gray'}">${esc(roleLabel(r))}</span>`;
  const statusPill = (active) => `<span class="pill ${active ? 'green' : 'red'}">${active ? 'Active' : 'Inactive'}</span>`;
  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Never');
  const safeNext = (n) => (n && n.startsWith('/') && !n.startsWith('//') ? n : '/dashboard/');
  const userEl = $('#lip-user');
  const user = userEl ? JSON.parse(userEl.textContent) : null;

  async function logout() {
    try { await api('/api/auth/logout/', { method: 'POST' }); } finally { location.href = '/login/'; }
  }

  document.addEventListener('click', (e) => {
    const soon = e.target.closest('[data-soon]');
    if (soon) { e.preventDefault(); toast(soon.dataset.soon + ' is part of an upcoming module.'); }
    if (e.target.closest('[data-logout]')) logout();
    if (e.target.closest('#menuBtn')) $('#sidebar').classList.toggle('open');
    const trigger = e.target.closest('.user-trigger');
    const menu = $('.user-dropdown');
    if (menu) menu.hidden = trigger ? !menu.hidden : true;
  });

  window.LIP = { $, $$, esc, api, ApiError, toast, confirm: confirmDialog, showErrors, clearErrors, busy, rolePill, statusPill, roleLabel, fmtDate, safeNext, user };
})();
