/* Inspector list, add/edit form and details page. */
(function () {
  'use strict';
  const { $, esc, api, showErrors, clearErrors, busy, rolePill, statusPill, fmtDate, toast } = LIP;
  const me = LIP.user;
  const isAdmin = me.role === 'admin';
  const FIELDS = ['username', 'email', 'first_name', 'last_name', 'role', 'employee_id', 'phone'];

  /* ---------- List ---------- */
  function initList() {
    const state = { page: 1 };
    const rows = $('#user-rows');
    let timer;

    async function load() {
      const p = new URLSearchParams({ page: state.page });
      [['q', '#f-q'], ['role', '#f-role'], ['is_active', '#f-active']].forEach(([k, sel]) => { if ($(sel).value.trim()) p.set(k, $(sel).value.trim()); });
      try {
        const data = await api('/api/users/?' + p);
        render(data);
      } catch (err) { rows.innerHTML = `<tr><td colspan="7" class="empty">${esc(err.message)}</td></tr>`; }
    }

    function render(data) {
      const list = data.results;
      rows.innerHTML = list.length ? list.map(rowHtml).join('') : '<tr><td colspan="7" class="empty">No users match your filters.</td></tr>';
      const size = 20, start = list.length ? (state.page - 1) * size + 1 : 0;
      $('#pager-info').textContent = `Showing ${start}–${start + list.length - (list.length ? 1 : 0)} of ${data.count}`;
      $('#prev').disabled = !data.previous;
      $('#next').disabled = !data.next;
    }

    function rowHtml(u) {
      const edit = isAdmin ? `<a class="btn secondary small" href="/users/${u.id}/edit/">Edit</a>` : '';
      const toggle = isAdmin && u.id !== me.id
        ? `<button class="btn ${u.is_active ? 'danger' : 'secondary'} small" data-toggle="${u.id}" data-active="${u.is_active}" data-name="${esc(u.full_name)}">${u.is_active ? 'Deactivate' : 'Activate'}</button>` : '';
      return `<tr><td><div class="cell-user"><span class="avatar sm">${esc(u.initials)}</span><div><div class="u">${esc(u.full_name)}</div><div class="m">@${esc(u.username)}</div></div></div></td>
        <td>${esc(u.email)}</td><td>${rolePill(u.role)}</td><td>${esc(u.employee_id || '—')}</td><td>${statusPill(u.is_active)}</td>
        <td>${esc(fmtDate(u.last_login))}</td><td><div class="actions"><a class="btn secondary small" href="/users/${u.id}/">View</a>${edit}${toggle}</div></td></tr>`;
    }

    rows.addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-toggle]');
      if (!btn) return;
      const activating = btn.dataset.active === 'false';
      const ok = await LIP.confirm({
        title: activating ? 'Activate account?' : 'Deactivate account?',
        message: activating ? `${btn.dataset.name} will be able to sign in again.` : `${btn.dataset.name} will no longer be able to sign in. Their inspection history is kept.`,
        confirmText: activating ? 'Activate' : 'Deactivate', danger: !activating,
      });
      if (!ok) return;
      try {
        await api(`/api/users/${btn.dataset.toggle}/${activating ? 'activate/' : ''}`, { method: activating ? 'POST' : 'DELETE' });
        toast(activating ? 'Account activated.' : 'Account deactivated.', 'success');
        load();
      } catch (err) { toast(err.message, 'error'); }
    });
    $('#f-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { state.page = 1; load(); }, 300); });
    ['#f-role', '#f-active'].forEach((s) => $(s).addEventListener('change', () => { state.page = 1; load(); }));
    $('#prev').addEventListener('click', () => { state.page -= 1; load(); });
    $('#next').addEventListener('click', () => { state.page += 1; load(); });
    load();
  }

  /* ---------- Add / Edit form ---------- */
  async function initForm(form) {
    const edit = form.dataset.mode === 'edit';
    const id = form.dataset.id;
    if (edit) {
      try {
        const u = await api(`/api/users/${id}/`);
        FIELDS.forEach((f) => { form.elements[f].value = u[f] ?? ''; });
        form.elements.is_active.value = String(u.is_active);
        form.elements.username.disabled = true;
      } catch (err) { showErrors(form, err); }
    }
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(form);
      const v = Object.fromEntries(new FormData(form));
      const btn = $('button[type=submit]', form);
      const body = {};
      FIELDS.forEach((f) => { if (!(edit && f === 'username')) body[f] = (v[f] || '').trim(); });
      if (!edit) {
        if (v.password !== v.confirm) return showErrors(form, { data: { confirm: ['Passwords do not match.'] } });
        body.password = v.password;
      } else { body.is_active = v.is_active === 'true'; }
      busy(btn, true, 'Saving…');
      try {
        const saved = await api(edit ? `/api/users/${id}/` : '/api/users/', { method: edit ? 'PATCH' : 'POST', body });
        toast(edit ? 'Changes saved.' : 'Account created.', 'success');
        setTimeout(() => { location.href = `/users/${saved.id}/`; }, 700);
      } catch (err) { showErrors(form, err); busy(btn, false); }
    });
  }

  /* ---------- Details ---------- */
  async function initDetail(box) {
    try {
      const u = await api(`/api/users/${box.dataset.id}/`);
      const actions = isAdmin ? `<a class="btn" href="/users/${u.id}/edit/">Edit</a>` : '';
      box.innerHTML = `<div class="profile-head"><div class="avatar lg">${esc(u.initials)}</div>
          <div style="flex:1"><h2>${esc(u.full_name)}</h2><div class="pills">${rolePill(u.role)}${statusPill(u.is_active)}</div></div>${actions}</div>
        <dl class="dl"><dt>Username</dt><dd>@${esc(u.username)}</dd><dt>Email</dt><dd>${esc(u.email)}</dd>
          <dt>Employee ID</dt><dd>${esc(u.employee_id || '—')}</dd><dt>Phone</dt><dd>${esc(u.phone || '—')}</dd>
          <dt>Last login</dt><dd>${esc(fmtDate(u.last_login))}</dd><dt>Account created</dt><dd>${esc(fmtDate(u.created_at))}</dd></dl>`;
    } catch (err) { box.innerHTML = `<div class="empty">${esc(err.status === 404 ? 'User not found.' : err.message)}</div>`; }
  }

  if ($('#user-rows')) initList();
  if ($('#user-form')) initForm($('#user-form'));
  if ($('#detail')) initDetail($('#detail'));
})();
