/* Profile (view/update, change password) and Roles & Permissions matrix. */
(function () {
  'use strict';
  const { $, esc, api, showErrors, clearErrors, busy, toast, rolePill } = LIP;

  async function initProfile() {
    const form = $('#profile-form');
    const pwForm = $('#password-form');
    try {
      const u = await api('/api/profile/');
      ['first_name', 'last_name', 'email', 'phone'].forEach((f) => { form.elements[f].value = u[f] || ''; });
      $('#p-role').innerHTML = rolePill(u.role);
    } catch (err) { showErrors(form, err); }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(form);
      const btn = $('button[type=submit]', form);
      busy(btn, true, 'Saving…');
      try {
        await api('/api/profile/', { method: 'PATCH', body: Object.fromEntries(new FormData(form)) });
        toast('Profile updated.', 'success');
        setTimeout(() => location.reload(), 600);  // refresh name/initials in the layout
      } catch (err) { showErrors(form, err); busy(btn, false); }
    });

    pwForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(pwForm);
      const v = Object.fromEntries(new FormData(pwForm));
      if (v.new_password !== v.confirm) return showErrors(pwForm, { data: { confirm: ['Passwords do not match.'] } });
      const btn = $('button[type=submit]', pwForm);
      busy(btn, true, 'Updating…');
      try {
        await api('/api/profile/change-password/', { method: 'POST', body: { old_password: v.old_password, new_password: v.new_password } });
        toast('Password changed.', 'success');
        pwForm.reset();
      } catch (err) { showErrors(pwForm, err); } finally { busy(btn, false); }
    });
  }

  const CELL = { yes: ['green', 'Yes'], no: ['red', 'No'], limited: ['amber', 'Limited'], permitted: ['amber', 'Permitted'] };

  async function initRoles() {
    try {
      const { roles, matrix } = await api('/api/roles/');
      $('#matrix-head').innerHTML = '<tr><th>Function</th>' + roles.map((r) => `<th class="center-cell">${esc(r.label)}</th>`).join('') + '</tr>';
      $('#matrix-body').innerHTML = Object.entries(matrix).map(([fn, perms]) =>
        `<tr><td><strong>${esc(fn)}</strong></td>` + roles.map((r) => {
          const [kind, text] = CELL[perms[r.value]] || ['gray', perms[r.value]];
          return `<td class="center-cell"><span class="pill ${kind}">${esc(text)}</span></td>`;
        }).join('') + '</tr>').join('');
    } catch (err) { $('#matrix-body').innerHTML = `<tr><td class="empty">${esc(err.message)}</td></tr>`; }
  }

  if ($('#profile-form')) initProfile();
  if ($('#matrix-body')) initRoles();
})();
