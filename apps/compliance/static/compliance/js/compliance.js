/* Compliance Rules screens (Module 4): overview, rule form, versions, categories, packs, evaluation, results, violations. */
(function () {
  'use strict';
  const { $, $$, esc, api, showErrors, clearErrors, busy, toast, confirm } = LIP;

  const SEV = { critical: 'red', major: 'amber', minor: 'gray' };
  const sevPill = (s) => `<span class="pill ${SEV[s] || 'gray'}">${esc(s ? s[0].toUpperCase() + s.slice(1) : '')}</span>`;
  const OUTCOME = {
    compliant: ['green', 'Compliant'], non_compliant: ['red', 'Non-Compliant'],
    requires_verification: ['amber', 'Requires Verification'], not_applicable: ['gray', 'Not Applicable'],
  };
  const outPill = (o) => `<span class="pill ${(OUTCOME[o] || ['gray'])[0]}">${esc((OUTCOME[o] || [0, o])[1])}</span>`;
  const STATE = { active: ['green', 'Active'], scheduled: ['amber', 'Scheduled'], draft: ['gray', 'Draft'], retired: ['red', 'Retired'], expired: ['red', 'Expired'] };
  const statePill = (s) => `<span class="pill ${(STATE[s] || ['gray'])[0]}">${esc((STATE[s] || [0, s])[1])}</span>`;
  const fmt = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—');
  const fmtDay = (iso) => (iso ? new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '—');
  const rows = (tbody, html, cols, empty) => { tbody.innerHTML = html || `<tr><td colspan="${cols}" class="empty">${empty}</td></tr>`; };
  const fail = (tbody, cols, err) => { tbody.innerHTML = `<tr><td colspan="${cols}" class="empty">${esc(err.message)}</td></tr>`; };

  function pager(state, data, load, shown) {
    const start = shown ? (state.page - 1) * 20 + 1 : 0;
    $('#pager-info').textContent = `Showing ${start}–${start + Math.max(shown - 1, 0)} of ${data.count}`;
    $('#prev').disabled = !data.previous;
    $('#next').disabled = !data.next;
  }
  function wirePager(state, load) {
    $('#prev').addEventListener('click', () => { state.page -= 1; load(); });
    $('#next').addEventListener('click', () => { state.page += 1; load(); });
  }
  function debounce(fn, ms = 300) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

  /* ================= Overview: stats, packs, rules ================= */
  function initOverview() {
    const state = { page: 1, pack: null, packName: '' };
    const packRows = $('#pack-rows');
    const ruleRows = $('#rule-rows');

    async function loadStats() {
      try {
        const s = await api('/api/rules/summary/');
        $('#st-rules').textContent = s.active_rules;
        $('#st-packs').textContent = s.rule_packs;
        $('#st-cats').textContent = s.categories;
      } catch (err) { toast(err.message, 'error'); }
    }

    async function loadPacks() {
      try {
        const packs = await api('/api/rule-packs/');
        rows(packRows, packs.map((p) => `<tr><td><a class="row-link" href="/rules/packs/${p.id}/" title="Manage this pack"><b>${esc(p.name)}</b></a></td><td>${esc(p.version)}</td><td>${p.rule_count}</td>
          <td>${esc(p.applies_to)}</td><td>${statePill(p.state)}</td>
          <td><button class="btn secondary small" data-view="${p.id}" data-name="${esc(p.name)} (${esc(p.version)})">View</button></td></tr>`).join(''), 6, 'No rule packs yet.');
        if (state.pack === null && packs.length) {
          const first = packs.find((p) => p.state === 'active') || packs[0];
          selectPack(first.id, `${first.name} (${first.version})`);
        }
      } catch (err) { fail(packRows, 6, err); }
    }

    function selectPack(id, name) {
      state.pack = id; state.packName = name; state.page = 1;
      $('#rules-title').textContent = id ? `Rules — ${name}` : 'Rules';
      loadRules();
    }

    async function loadRules() {
      const p = new URLSearchParams({ page: state.page });
      if (state.pack) p.set('pack', state.pack);
      try {
        const data = await api('/api/rules/?' + p);
        rows(ruleRows, data.results.map((r) => `<tr><td><a class="row-link" href="/rules/${r.id}/edit/" title="Edit this rule">${esc(r.code)}</a></td><td>${esc(r.title)}</td>
          <td>${esc(r.category_name)}</td><td>${sevPill(r.severity)}</td><td>${LIP.statusPill(r.is_active)}</td></tr>`).join(''),
        5, 'No rules in this pack yet.');
        $('#rule-pager').hidden = !(data.next || data.previous);
        pager(state, data, loadRules, data.results.length);
      } catch (err) { fail(ruleRows, 5, err); }
    }

    packRows.addEventListener('click', (e) => {
      const b = e.target.closest('[data-view]');
      if (b) selectPack(Number(b.dataset.view), b.dataset.name);
    });
    wirePager(state, loadRules);
    loadStats();
    loadPacks();
  }

  /* ================= Rule form ================= */
  const TYPE_LABEL = {
    required: 'Required fields must be filled in',
    contains_any: 'Text must contain one of these words',
    manual_check: 'Inspector checks the physical label',
    not_expired: 'Date must not be expired',
    quantity_format: 'Net quantity must be a number with a unit',
    date_valid: 'Dates must be in a valid format',
    date_order: 'One date must not be before another',
    numeric_min: 'Number must be above a minimum',
    regex: 'Text must match a pattern (advanced)',
  };
  const TYPE_ORDER = ['required', 'contains_any', 'manual_check', 'not_expired', 'quantity_format', 'date_valid', 'date_order', 'numeric_min', 'regex'];
  const TYPE_HINT = {
    required: 'Tick the particulars that must be declared on the label.',
    contains_any: 'The text of the ticked fields must contain at least one of your words or phrases.',
    manual_check: 'The app cannot read this from the data, so the inspector is asked to look at the pack.',
    not_expired: 'The date must not be before the day of the inspection.',
    quantity_format: 'Net quantity must look like "500 g" or "1 L".',
    date_valid: 'Each filled date must be DD/MM/YY, DD/MM/YYYY or MMM/YYYY.',
    date_order: 'The second date must not be earlier than the first (for example expiry after manufacture).',
    numeric_min: 'The number must be above (or at least) the minimum you set.',
    regex: 'For experts: the text must match a regular expression such as a 14-digit number.',
  };
  const DATE_FIELDS = ['manufacturing_date', 'best_before', 'expiry_date'];
  const COND_OPS = { present: 'is filled in', absent: 'is empty', contains_any: 'contains any of', not_contains_any: 'does not contain any of' };
  const MISSING_OPTS = '<option value="not_applicable">Skip the rule (Not Applicable)</option><option value="fail">Treat as a failure</option><option value="requires_verification">Ask the inspector to verify</option>';
  const MANAGED = {
    required: ['fields', 'field', 'mode'], contains_any: ['fields', 'field', 'keywords'], regex: ['fields', 'field', 'pattern', 'expect'],
    quantity_format: ['fields', 'field', 'on_missing'], not_expired: ['fields', 'field', 'on_missing'], date_valid: ['fields', 'field', 'on_missing'],
    date_order: ['first_field', 'second_field'], numeric_min: ['fields', 'field', 'min', 'exclusive', 'on_missing'], manual_check: ['prompt'],
  };

  async function initRuleForm(form) {
    const edit = form.dataset.mode === 'edit';
    const id = form.dataset.id;
    const meta = await api('/api/rules/meta/');
    const FIELDS = meta.data_fields; // key -> label
    const fieldKeys = Object.keys(FIELDS);
    const box = $('#guided-box');
    let extra = {}; // saved settings the guided form has no control for (e.g. fail_detail) are kept as they are

    $('#category').innerHTML = '<option value="">Choose…</option>' + meta.categories.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
    const types = TYPE_ORDER.filter((t) => meta.rule_types.includes(t)).concat(meta.rule_types.filter((t) => !TYPE_ORDER.includes(t)));
    $('#rule_type').innerHTML = types.map((t) => `<option value="${t}">${esc(TYPE_LABEL[t] || t.replace(/_/g, ' '))}</option>`).join('');
    $('#fields-hint').textContent = 'Data fields: ' + fieldKeys.join(', ');

    const opts = (keys, selected) => keys.map((k) => `<option value="${k}"${k === selected ? ' selected' : ''}>${esc(FIELDS[k] || k)}</option>`).join('');
    const checks = (keys, picked) => `<div class="check-grid">${keys.map((k) => `<label class="check-row"><input type="checkbox" name="g-field" value="${k}"${picked.includes(k) ? ' checked' : ''}> ${esc(FIELDS[k])}</label>`).join('')}</div>`;
    const listOf = (p) => { const raw = p.fields || p.field || []; return Array.isArray(raw) ? raw : [raw]; };
    const missingSelect = (p) => `<div class="g-row"><label for="g-missing">If the field is empty</label><select id="g-missing">${MISSING_OPTS}</select></div>`;
    const setMissing = (p) => { const el = $('#g-missing'); if (el) el.value = p.on_missing || 'not_applicable'; };

    /* ----- guided panel for each check type ----- */
    function renderGuided(type, p) {
      p = p || {};
      const picked = listOf(p);
      let html = '';
      if (type === 'required') {
        html = `<label>Fields that must be filled in</label>${checks(fieldKeys, picked)}
          <div class="g-row"><label for="g-mode">Rule is met when</label><select id="g-mode"><option value="all">every ticked field is filled</option><option value="any">at least one ticked field is filled</option></select></div>`;
      } else if (type === 'contains_any') {
        html = `<label>Fields to look in</label>${checks(fieldKeys, picked)}
          <div class="g-row"><label for="g-keywords">Words or phrases (separate with commas)</label><input id="g-keywords" placeholder="e.g. batch, lot, b.no"></div>`;
      } else if (type === 'manual_check') {
        html = '<div class="g-row"><label for="g-prompt">What should the inspector check on the pack?</label><textarea id="g-prompt" style="min-height:80px" placeholder="e.g. Check the green veg symbol is on the front of the pack."></textarea></div>';
      } else if (type === 'not_expired') {
        html = `<div class="g-row"><label for="g-field">Date to check</label><select id="g-field">${opts(DATE_FIELDS, picked[0] || 'expiry_date')}</select></div>${missingSelect(p)}`;
      } else if (type === 'quantity_format') {
        html = `<div class="g-row"><label for="g-field">Field</label><select id="g-field">${opts(['net_quantity'], 'net_quantity')}</select></div>${missingSelect(p)}`;
      } else if (type === 'date_valid') {
        html = `<label>Dates to check</label>${checks(DATE_FIELDS, picked)}${missingSelect(p)}`;
      } else if (type === 'date_order') {
        html = `<div class="g-row"><label for="g-first">Earlier date</label><select id="g-first">${opts(DATE_FIELDS, p.first_field || 'manufacturing_date')}</select></div>
          <div class="g-row"><label for="g-second">Later date</label><select id="g-second">${opts(DATE_FIELDS, p.second_field || 'expiry_date')}</select></div>`;
      } else if (type === 'numeric_min') {
        html = `<div class="g-row"><label for="g-field">Number to check</label><select id="g-field">${opts(['mrp', 'net_quantity'], picked[0] || 'mrp')}</select></div>
          <div class="g-row"><label for="g-min">Minimum</label><input id="g-min" type="number" step="any" value="${p.min ?? 0}"></div>
          <label class="check-row"><input type="checkbox" id="g-exclusive"${p.exclusive === false ? '' : ' checked'}> Must be strictly more than the minimum</label>${missingSelect(p)}`;
      } else if (type === 'regex') {
        html = `<label>Fields to check</label>${checks(fieldKeys, picked)}
          <div class="g-row"><label for="g-pattern">Pattern (regular expression)</label><input id="g-pattern" class="code-area" style="min-height:0" placeholder="e.g. \\d{14}"></div>
          <div class="g-row"><label for="g-expect">Rule is met when the text</label><select id="g-expect"><option value="match">matches the pattern</option><option value="no_match">does not match the pattern</option></select></div>${missingSelect(p)}`;
      }
      box.innerHTML = html;
      if ($('#g-mode')) $('#g-mode').value = p.mode || 'all';
      if ($('#g-keywords')) $('#g-keywords').value = (p.keywords || []).join(', ');
      if ($('#g-prompt')) $('#g-prompt').value = p.prompt || '';
      if ($('#g-pattern')) $('#g-pattern').value = p.pattern || '';
      if ($('#g-expect')) $('#g-expect').value = p.expect || 'match';
      setMissing(p);
      $('#type-hint').textContent = TYPE_HINT[type] || '';
      const known = MANAGED[type] || [];
      extra = Object.fromEntries(Object.entries(p).filter(([k]) => !known.includes(k)));
    }

    const ticked = () => $$('input[name=g-field]:checked', box).map((c) => c.value);
    /** Read the guided panel into a parameters object; returns {params} or {error}. */
    function readGuided(type) {
      const params = { ...extra };
      const missing = $('#g-missing') ? $('#g-missing').value : null;
      if (missing && missing !== 'not_applicable') params.on_missing = missing;
      const need = (list, msg) => (list.length ? null : { error: msg });
      if (type === 'required') {
        const f = ticked(); const e = need(f, 'Tick at least one field that must be filled in.'); if (e) return e;
        params.fields = f; if ($('#g-mode').value !== 'all') params.mode = $('#g-mode').value; // "all" is the default
      } else if (type === 'contains_any') {
        const f = ticked(); let e = need(f, 'Tick at least one field to look in.'); if (e) return e;
        const kw = $('#g-keywords').value.split(',').map((x) => x.trim()).filter(Boolean);
        e = need(kw, 'Type at least one word or phrase.'); if (e) return e;
        params.fields = f; params.keywords = kw;
      } else if (type === 'manual_check') {
        const t = $('#g-prompt').value.trim(); if (!t) return { error: 'Tell the inspector what to check on the pack.' };
        params.prompt = t;
      } else if (type === 'not_expired' || type === 'quantity_format') {
        params.field = $('#g-field').value;
      } else if (type === 'date_valid') {
        const f = ticked(); const e = need(f, 'Tick at least one date.'); if (e) return e;
        params.fields = f;
      } else if (type === 'date_order') {
        if ($('#g-first').value === $('#g-second').value) return { error: 'Choose two different dates.' };
        params.first_field = $('#g-first').value; params.second_field = $('#g-second').value;
      } else if (type === 'numeric_min') {
        params.field = $('#g-field').value; params.min = Number($('#g-min').value || 0); if (!$('#g-exclusive').checked) params.exclusive = false; // true is the default
      } else if (type === 'regex') {
        const f = ticked(); let e = need(f, 'Tick at least one field to check.'); if (e) return e;
        const pat = $('#g-pattern').value.trim(); if (!pat) return { error: 'Type the pattern to match.' };
        params.fields = f; params.pattern = pat; if ($('#g-expect').value !== 'match') params.expect = $('#g-expect').value;
      }
      return { params };
    }

    /* ----- "applies only when" conditions ----- */
    const condRows = $('#cond-rows');
    function addCond(c) {
      c = c || { field: fieldKeys[0], op: 'present' };
      const names = Array.isArray(c.field) ? c.field : [c.field];
      const value = names.join(',');
      const fieldOpts = fieldKeys.map((k) => `<option value="${k}">${esc(FIELDS[k])}</option>`).join('') +
        (names.length > 1 ? `<option value="${esc(value)}">${esc(names.map((n) => FIELDS[n] || n).join(' / '))} (combined)</option>` : '');
      const row = document.createElement('div');
      row.className = 'cond-row';
      row.innerHTML = `<select class="c-field" aria-label="Field">${fieldOpts}</select>
        <select class="c-op" aria-label="Condition">${Object.entries(COND_OPS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
        <input class="c-values" placeholder="words, separated by commas" aria-label="Words">
        <button class="btn secondary small" type="button" data-rm aria-label="Remove condition">✕</button>`;
      condRows.appendChild(row);
      $('.c-field', row).value = value;
      $('.c-op', row).value = c.op;
      $('.c-values', row).value = (c.values || []).join(', ');
      syncCond(row);
    }
    function syncCond(row) { $('.c-values', row).hidden = ['present', 'absent'].includes($('.c-op', row).value); }
    function setConditions(list) {
      condRows.innerHTML = '';
      (list || []).forEach(addCond);
      $('#apply-mode').value = (list || []).length ? 'some' : 'all';
      $('#conditions').hidden = !(list || []).length;
    }
    function readConditions() {
      if ($('#apply-mode').value === 'all') return { list: [] };
      const list = [];
      for (const row of $$('.cond-row', condRows)) {
        const field = $('.c-field', row).value; const op = $('.c-op', row).value;
        const cond = { field: field.includes(',') ? field.split(',') : field, op };
        if (!['present', 'absent'].includes(op)) {
          const values = $('.c-values', row).value.split(',').map((x) => x.trim()).filter(Boolean);
          if (!values.length) return { error: 'Type at least one word for each "contains" condition.' };
          cond.values = values;
        }
        list.push(cond);
      }
      if (!list.length) return { error: 'Add a condition, or choose "To every product".' };
      return { list };
    }
    $('#apply-mode').addEventListener('change', () => {
      const some = $('#apply-mode').value === 'some';
      $('#conditions').hidden = !some;
      if (some && !$$('.cond-row', condRows).length) addCond();
    });
    $('#add-cond').addEventListener('click', () => addCond());
    condRows.addEventListener('change', (e) => { const row = e.target.closest('.cond-row'); if (row) syncCond(row); });
    condRows.addEventListener('click', (e) => {
      const rm = e.target.closest('[data-rm]');
      if (rm) { rm.closest('.cond-row').remove(); if (!$$('.cond-row', condRows).length) { $('#apply-mode').value = 'all'; $('#conditions').hidden = true; } }
    });

    $('#rule_type').addEventListener('change', () => renderGuided($('#rule_type').value, {}));

    /* ----- advanced (JSON) switch ----- */
    const adv = $('#advanced');
    function showAdvanced(on) {
      $('#advanced-box').hidden = !on;
      box.hidden = on; $('#apply-box').hidden = on;
    }
    adv.addEventListener('change', () => {
      clearErrors(form);
      if (adv.checked) {
        const g = readGuided($('#rule_type').value); const c = readConditions();
        form.elements.parameters.value = JSON.stringify(g.params || extra, null, 2);
        form.elements.applies_when.value = (c.list || []).length ? JSON.stringify(c.list, null, 2) : '[]';
        showAdvanced(true);
      } else {
        try {
          const p = JSON.parse(form.elements.parameters.value || '{}');
          const text = form.elements.applies_when.value.trim();
          const list = text ? JSON.parse(text) : [];
          if (!p || typeof p !== 'object' || Array.isArray(p) || !Array.isArray(list)) throw new Error('shape');
          renderGuided($('#rule_type').value, p); setConditions(list); showAdvanced(false);
        } catch (_) {
          adv.checked = true;
          showErrors(form, { data: { _banner: 'The JSON is not valid, so the simple form cannot show it. Fix the JSON or keep Advanced on.' } });
        }
      }
    });

    /* ----- load ----- */
    if (edit) {
      try {
        const r = await api(`/api/rules/${id}/`);
        ['code', 'title', 'category', 'severity', 'regulation_ref', 'description', 'rule_type', 'on_fail', 'failure_message'].forEach((f) => { form.elements[f].value = r[f] ?? ''; });
        form.elements.is_active.checked = r.is_active;
        renderGuided(r.rule_type, r.parameters || {});
        setConditions(r.applies_when || []);
      } catch (err) { showErrors(form, err); }
    } else {
      renderGuided($('#rule_type').value, {});
      setConditions([]);
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(form);
      const body = {};
      ['code', 'title', 'severity', 'regulation_ref', 'description', 'rule_type', 'on_fail', 'failure_message'].forEach((f) => { body[f] = form.elements[f].value.trim(); });
      body.category = form.elements.category.value || null;
      body.is_active = form.elements.is_active.checked;
      if (edit) { body.change_note = form.elements.change_note.value.trim(); delete body.code; } else if (!body.code) { delete body.code; }
      if (adv.checked) {
        try { body.parameters = JSON.parse(form.elements.parameters.value || '{}'); } catch (_) { showErrors(form, { data: { parameters: ['Parameters are not valid JSON.'] } }); return; }
        try { const text = form.elements.applies_when.value.trim(); body.applies_when = text ? JSON.parse(text) : []; } catch (_) { showErrors(form, { data: { applies_when: ['This is not valid JSON.'] } }); return; }
      } else {
        const g = readGuided(body.rule_type);
        if (g.error) { showErrors(form, { data: { _banner: g.error } }); return; }
        const c = readConditions();
        if (c.error) { showErrors(form, { data: { _banner: c.error } }); return; }
        body.parameters = g.params; body.applies_when = c.list;
      }
      const btn = $('button[type=submit]', form);
      busy(btn, true, 'Saving…');
      try {
        const saved = await api(edit ? `/api/rules/${id}/` : '/api/rules/', { method: edit ? 'PUT' : 'POST', body });
        toast(edit ? `Rule saved (version ${saved.version_number}).` : `Rule ${saved.code} added.`, 'success');
        setTimeout(() => { location.href = '/rules/'; }, 600);
      } catch (err) {
        if (!adv.checked && err.data && typeof err.data === 'object' && (err.data.parameters || err.data.applies_when)) {
          const msg = [].concat(err.data.parameters || [], err.data.applies_when || []).join(' ');
          showErrors(form, { data: { _banner: msg } });
        } else { showErrors(form, err); }
        busy(btn, false);
      }
    });

    const del = $('#delete-rule');
    if (del) del.addEventListener('click', async () => {
      if (!(await confirm({ title: 'Delete rule?', message: 'Only rules that no pack or result uses can be deleted. Otherwise deactivate it.', confirmText: 'Delete', danger: true }))) return;
      try { await api(`/api/rules/${id}/`, { method: 'DELETE' }); toast('Rule deleted.', 'success'); setTimeout(() => { location.href = '/rules/'; }, 500); } catch (err) { toast(err.message, 'error'); }
    });
  }

  /* ================= Versions ================= */
  async function initVersions(card) {
    const id = card.dataset.id;
    const body = $('#version-rows');
    try {
      const [rule, versions] = await Promise.all([api(`/api/rules/${id}/`), api(`/api/rules/${id}/versions/`)]);
      $('#ver-title').innerHTML = `${esc(rule.code)} — ${esc(rule.title)}`;
      rows(body, versions.map((v) => `<tr><td><b>v${v.version_number}</b> ${v.is_current ? '<span class="pill green">Current</span>' : ''}</td><td>${esc(v.rule_type.replace(/_/g, ' '))}</td>
        <td>${outPill(v.on_fail)}</td><td><pre class="params">${esc(JSON.stringify(v.parameters, null, 1))}${v.applies_when.length ? '\nApplies when: ' + esc(JSON.stringify(v.applies_when)) : ''}</pre></td>
        <td>${esc(v.change_note || '—')}</td><td>${esc(fmt(v.created_at))}<div class="cell-sub">${esc(v.created_by_name || 'System')}</div></td></tr>`).join(''), 6, 'No versions.');
    } catch (err) { fail(body, 6, err); }
  }

  /* ================= Categories ================= */
  function initCategories() {
    const form = $('#cat-form');
    const body = $('#cat-rows');
    let editing = null;
    let cache = [];

    async function load() {
      try {
        cache = await api('/api/rule-categories/');
        rows(body, cache.map((c) => `<tr><td><b>${esc(c.name)}</b></td><td>${esc(c.description || '—')}</td><td>${c.rule_count}</td><td>${LIP.statusPill(c.is_active)}</td>
          <td><div class="actions"><button class="btn secondary small" data-edit="${c.id}">Edit</button><button class="btn danger small" data-del="${c.id}">Delete</button></div></td></tr>`).join(''), 5, 'No categories yet.');
      } catch (err) { fail(body, 5, err); }
    }
    function reset() {
      editing = null; form.reset(); clearErrors(form);
      $('#cat-form-title').textContent = 'Add category'; $('#cat-save').textContent = 'Add category'; $('#cat-cancel').hidden = true;
    }
    body.addEventListener('click', async (e) => {
      const ed = e.target.closest('[data-edit]');
      const del = e.target.closest('[data-del]');
      if (ed) {
        const c = cache.find((x) => x.id === Number(ed.dataset.edit));
        editing = c.id; form.elements.name.value = c.name; form.elements.description.value = c.description || '';
        $('#cat-form-title').textContent = 'Edit category'; $('#cat-save').textContent = 'Save category'; $('#cat-cancel').hidden = false;
        form.elements.name.focus();
      }
      if (del) {
        if (!(await confirm({ title: 'Delete category?', message: 'A category that still has rules cannot be deleted.', confirmText: 'Delete', danger: true }))) return;
        try { await api(`/api/rule-categories/${del.dataset.del}/`, { method: 'DELETE' }); toast('Category deleted.', 'success'); load(); } catch (err) { toast(err.message, 'error'); }
      }
    });
    $('#cat-cancel').addEventListener('click', reset);
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); clearErrors(form);
      const payload = { name: form.elements.name.value.trim(), description: form.elements.description.value.trim() };
      const btn = $('#cat-save'); busy(btn, true, 'Saving…');
      try {
        await api(editing ? `/api/rule-categories/${editing}/` : '/api/rule-categories/', { method: editing ? 'PATCH' : 'POST', body: payload });
        toast(editing ? 'Category updated.' : 'Category added.', 'success'); reset(); load();
      } catch (err) { showErrors(form, err); }
      busy(btn, false);
    });
    load();
  }

  /* ================= Pack form + items ================= */
  async function initPackForm(form) {
    const edit = form.dataset.mode === 'edit';
    const id = form.dataset.id;
    const FIELDS = ['name', 'version', 'applies_to', 'status', 'regulation_ref', 'effective_from', 'effective_to', 'description'];

    async function loadExtendsOptions(selected) {
      try {
        const packs = await api('/api/rule-packs/');
        form.elements.extends.innerHTML = '<option value="">— None —</option>' + packs
          .filter((x) => String(x.id) !== String(id) && !x.extends)
          .map((x) => `<option value="${x.id}">${esc(x.name)} (${esc(x.version)})</option>`).join('');
        form.elements.extends.value = selected || '';
      } catch (err) { /* the field simply stays on None */ }
    }
    function fill(p) {
      FIELDS.forEach((f) => { form.elements[f].value = p[f] ?? ''; });
      loadExtendsOptions(p.extends);
      form.elements.product_categories.value = (p.product_categories || []).join(', ');
    }
    function renderItems(p) {
      const body = $('#item-rows');
      $('#items-sub').innerHTML = `${p.items.length} rules · ${statePill(p.state)}`;
      rows(body, p.items.map((i) => `<tr><td class="mono">${esc(i.code)}</td><td><b>${esc(i.title)}</b>${i.is_active ? '' : ' <span class="pill red">Inactive</span>'}</td><td>${esc(i.category_name)}</td><td>${sevPill(i.severity)}</td>
        <td>v${i.version_number}${i.latest_version > i.version_number ? ` <span class="pill amber">v${i.latest_version} available</span>` : ''}</td>
        <td><div class="actions"><button class="btn danger small" data-remove="${i.rule}">Remove</button></div></td></tr>`).join(''), 6, 'No rules in this pack yet. Add some below.');
      return p;
    }
    async function loadAddList(p) {
      const inPack = new Set(p.items.map((i) => i.rule));
      const all = [];
      for (let page = 1; page <= 20; page += 1) {
        const d = await api(`/api/rules/?page=${page}`);
        all.push(...d.results);
        if (!d.next) break;
      }
      $('#add-rule').innerHTML = '<option value="">Choose a rule to add…</option>' + all.filter((r) => !inPack.has(r.id)).map((r) => `<option value="${r.id}">${esc(r.code)} — ${esc(r.title)}</option>`).join('');
    }

    if (!edit) loadExtendsOptions('');
    if (edit) {
      try {
        const p = await api(`/api/rule-packs/${id}/`);
        fill(p); renderItems(p); loadAddList(p);
      } catch (err) { showErrors(form, err); }

      $('#item-rows').addEventListener('click', async (e) => {
        const b = e.target.closest('[data-remove]');
        if (!b) return;
        try { const p = await api(`/api/rule-packs/${id}/remove-rule/`, { method: 'POST', body: { rule: Number(b.dataset.remove) } }); renderItems(p); loadAddList(p); } catch (err) { toast(err.message, 'error'); }
      });
      $('#add-rule-btn').addEventListener('click', async () => {
        const rule = $('#add-rule').value;
        if (!rule) { toast('Choose a rule first.', 'error'); return; }
        try { const p = await api(`/api/rule-packs/${id}/add-rule/`, { method: 'POST', body: { rule: Number(rule) } }); renderItems(p); loadAddList(p); toast('Rule added.', 'success'); } catch (err) { toast(err.message, 'error'); }
      });
      $('#refresh-pack').addEventListener('click', async () => {
        try {
          const p = await api(`/api/rule-packs/${id}/refresh/`, { method: 'POST' });
          renderItems(p); toast(p.refreshed ? `${p.refreshed} rule(s) moved to their latest version.` : 'Already on the latest versions.', 'success');
        } catch (err) { toast(err.message, 'error'); }
      });
      const del = $('#delete-pack');
      del.addEventListener('click', async () => {
        if (!(await confirm({ title: 'Delete pack?', message: 'A pack that has been used in evaluations cannot be deleted; retire it instead.', confirmText: 'Delete', danger: true }))) return;
        try { await api(`/api/rule-packs/${id}/`, { method: 'DELETE' }); toast('Pack deleted.', 'success'); setTimeout(() => { location.href = '/rules/'; }, 500); } catch (err) { toast(err.message, 'error'); }
      });
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault(); clearErrors(form);
      const body = {};
      FIELDS.forEach((f) => { body[f] = form.elements[f].value.trim(); });
      body.effective_from = body.effective_from || null;
      body.effective_to = body.effective_to || null;
      body.extends = form.elements.extends.value ? Number(form.elements.extends.value) : null;
      body.product_categories = form.elements.product_categories.value.split(',').map((s) => s.trim()).filter(Boolean);
      const btn = $('button[type=submit]', form); busy(btn, true, 'Saving…');
      try {
        const saved = await api(edit ? `/api/rule-packs/${id}/` : '/api/rule-packs/', { method: edit ? 'PUT' : 'POST', body });
        toast(edit ? 'Pack saved.' : 'Pack created. Now add its rules.', 'success');
        if (!edit) setTimeout(() => { location.href = `/rules/packs/${saved.id}/`; }, 600); else busy(btn, false);
      } catch (err) { showErrors(form, err); busy(btn, false); }
    });
  }

  /* ================= Test evaluation ================= */
  const SAMPLE = {
    product_name: 'Salted Butter', brand: 'Demo Dairy', mrp: '270.00', net_quantity: '500 g', manufacturing_date: '01/09/2026',
    expiry_date: '01/03/2027', fssai_license: '10012345678901', ingredients: 'Milk fat, common salt',
    manufacturer: 'Demo Dairy Pvt Ltd, Anand, Gujarat 388001',
    other_declarations: 'Contains milk. Batch No. B123. Consumer care: 1800-000-000.',
  };
  async function initEvaluate(form) {
    api('/api/rule-packs/').then((packs) => {
      $('#pack').insertAdjacentHTML('beforeend', packs.filter((p) => p.status !== 'draft').map((p) => `<option value="${p.id}">${esc(p.name)} (${esc(p.version)})</option>`).join(''));
    }).catch(() => {});
    $('#fill-sample').addEventListener('click', () => { Object.entries(SAMPLE).forEach(([k, v]) => { form.elements[k].value = v; }); });
    form.addEventListener('submit', async (e) => {
      e.preventDefault(); clearErrors(form);
      const data = {};
      ['product_name', 'brand', 'mrp', 'net_quantity', 'manufacturing_date', 'expiry_date', 'best_before', 'fssai_license', 'ingredients', 'manufacturer', 'packer', 'importer', 'other_declarations']
        .forEach((f) => { data[f] = form.elements[f].value.trim(); });
      const body = { data, reference: form.elements.reference.value.trim(), category: form.elements.category.value.trim() };
      if (form.elements.pack.value) body.pack = Number(form.elements.pack.value);
      if (form.elements.reference_date.value) body.reference_date = form.elements.reference_date.value;
      const btn = $('button[type=submit]', form); busy(btn, true, 'Evaluating…');
      try {
        const r = await api('/api/compliance/evaluate/', { method: 'POST', body });
        location.href = `/rules/results/${r.id}/`;
      } catch (err) { showErrors(form, err); busy(btn, false); }
    });
  }

  /* ================= Results ================= */
  function initResultList() {
    const state = { page: 1 };
    const body = $('#result-rows');
    async function load() {
      const p = new URLSearchParams({ page: state.page });
      if ($('#f-q').value.trim()) p.set('q', $('#f-q').value.trim());
      if ($('#f-status').value) p.set('status', $('#f-status').value);
      try {
        const data = await api('/api/compliance/results/?' + p);
        rows(body, data.results.map((r) => `<tr><td class="mono">#${r.id}</td><td>${esc(r.reference || '—')}</td><td>${esc(r.pack_name)}<div class="cell-sub">${esc(r.pack_version)}</div></td>
          <td>${outPill(r.overall_status)}</td><td>${r.non_compliant_count}</td><td>${esc(fmt(r.evaluated_at))}<div class="cell-sub">${esc(r.evaluated_by_name)}</div></td>
          <td><a class="btn secondary small" href="/rules/results/${r.id}/">View</a></td></tr>`).join(''), 7, 'No evaluations yet.');
        pager(state, data, load, data.results.length);
      } catch (err) { fail(body, 7, err); }
    }
    $('#f-q').addEventListener('input', debounce(() => { state.page = 1; load(); }));
    $('#f-status').addEventListener('change', () => { state.page = 1; load(); });
    wirePager(state, load);
    load();
  }

  async function initResultDetail(box) {
    try {
      const r = await api(`/api/compliance/results/${box.dataset.id}/`);
      const [, label] = OUTCOME[r.overall_status] || [0, r.overall_status];
      const d = r.data_snapshot || {};
      const dataRows = Object.entries(d).filter(([, v]) => v).map(([k, v]) => `<dt>${esc(k.replace(/_/g, ' '))}</dt><dd>${esc(v)}</dd>`).join('');
      const needs = r.evaluations.filter((e) => e.outcome === 'requires_verification');
      const evalRow = (e) => `<tr><td class="mono">${esc(e.rule_code)}</td><td><b>${esc(e.rule_title)}</b><div class="cell-sub">${esc(e.regulation_ref)} · v${e.version_number}</div></td>
        <td>${esc(e.category_name)}</td><td>${sevPill(e.severity)}</td><td>${outPill(e.outcome)}</td><td>${esc(e.detail)}</td></tr>`;
      box.innerHTML = `<div class="result-banner ${esc(r.overall_status)}"><div><div class="muted">Overall result</div><div class="big">${esc(label)}</div></div>
          <div class="muted">${esc(r.pack_name)} (${esc(r.pack_version)})<br>${esc(r.reference || 'No reference')} · as on ${esc(fmtDay(r.reference_date))}</div>
          <div class="counts"><span><b>${r.compliant_count}</b> compliant</span><span><b>${r.non_compliant_count}</b> non-compliant</span><span><b>${r.verification_count}</b> to verify</span><span><b>${r.not_applicable_count}</b> n/a</span></div></div>
        ${r.violations.length ? `<div class="card"><div class="card-head"><h2>Violations (${r.violations.length})</h2></div><div class="table-wrap"><table><thead><tr><th>Rule ID</th><th>Violation</th><th>Severity</th><th>Regulation</th></tr></thead><tbody>
          ${r.violations.map((v) => `<tr><td class="mono">${esc(v.rule_code)}</td><td><b>${esc(v.rule_title)}</b><div class="cell-sub">${esc(v.message)}</div></td><td>${sevPill(v.severity)}</td><td>${esc(v.regulation_ref)}</td></tr>`).join('')}</tbody></table></div></div>` : ''}
        ${needs.length ? `<div class="alert info">${needs.length} check(s) need the inspector to verify against the physical label.</div>` : ''}
        <div class="card"><div class="card-head"><h2>All rule outcomes</h2></div><div class="table-wrap"><table><thead><tr><th>Rule ID</th><th>Rule</th><th>Category</th><th>Severity</th><th>Outcome</th><th>Detail</th></tr></thead><tbody>${r.evaluations.map(evalRow).join('')}</tbody></table></div></div>
        <div class="card"><div class="card-head"><h2>Verified data evaluated</h2><span class="muted">Evaluated ${esc(fmt(r.evaluated_at))} by ${esc(r.evaluated_by_name || '—')}</span></div><dl class="dl">${dataRows || '<dt>—</dt><dd>No data</dd>'}</dl></div>`;
    } catch (err) { box.innerHTML = `<div class="card"><div class="empty">${esc(err.status === 404 ? 'Result not found.' : err.message)}</div></div>`; }
  }

  /* ================= Violations ================= */
  function initViolations() {
    const state = { page: 1 };
    const body = $('#violation-rows');
    async function load() {
      const p = new URLSearchParams({ page: state.page });
      if ($('#f-q').value.trim()) p.set('q', $('#f-q').value.trim());
      if ($('#f-severity').value) p.set('severity', $('#f-severity').value);
      try {
        const data = await api('/api/compliance/violations/?' + p);
        rows(body, data.results.map((v) => `<tr><td class="mono">${esc(v.rule_code)}</td><td><b>${esc(v.rule_title)}</b><div class="cell-sub">${esc(v.message)}</div></td><td>${sevPill(v.severity)}</td>
          <td>${esc(v.reference || '—')}</td><td>${esc(v.pack_name)}</td><td>${esc(fmt(v.created_at))}</td><td><a class="btn secondary small" href="/rules/results/${v.result_id}/">Result</a></td></tr>`).join(''), 7, 'No violations recorded.');
        pager(state, data, load, data.results.length);
      } catch (err) { fail(body, 7, err); }
    }
    $('#f-q').addEventListener('input', debounce(() => { state.page = 1; load(); }));
    $('#f-severity').addEventListener('change', () => { state.page = 1; load(); });
    wirePager(state, load);
    load();
  }

  if ($('#pack-rows')) initOverview();
  if ($('#rule-form')) initRuleForm($('#rule-form'));
  if ($('#versions-card')) initVersions($('#versions-card'));
  if ($('#cat-form')) initCategories();
  if ($('#pack-form')) initPackForm($('#pack-form'));
  if ($('#eval-form')) initEvaluate($('#eval-form'));
  if ($('#result-rows')) initResultList();
  if ($('#result-detail')) initResultDetail($('#result-detail'));
  if ($('#violation-rows')) initViolations();
})();
