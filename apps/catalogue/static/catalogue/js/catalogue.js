/* Product Catalogue (Module 2): list + search, Manual Product Entry card (add / edit) and details. */
(function () {
  'use strict';
  const { $, esc, api, showErrors, clearErrors, busy, toast } = LIP;
  const FIELDS = ['name', 'brand', 'gtin', 'net_quantity', 'category', 'manufacturer'];

  /* ---------- List + search + entry card ---------- */
  function initList() {
    const state = { page: 1 };
    const rows = $('#product-rows');
    const card = $('#entry-card');
    const form = $('#product-form');
    let timer;
    let editing = null; // product id being edited, or null when adding

    async function load() {
      const p = new URLSearchParams({ page: state.page });
      [['q', '#f-q'], ['category', '#f-category']].forEach(([k, sel]) => { if ($(sel).value.trim()) p.set(k, $(sel).value.trim()); });
      try {
        const data = await api('/api/products/?' + p);
        rows.innerHTML = data.results.length ? data.results.map(rowHtml).join('') : '<tr><td colspan="6" class="empty">No products found. Try another search or add a product.</td></tr>';
        const start = data.results.length ? (state.page - 1) * 20 + 1 : 0;
        $('#pager-info').textContent = `Showing ${start}–${start + Math.max(data.results.length - 1, 0)} of ${data.count}`;
        $('#prev').disabled = !data.previous;
        $('#next').disabled = !data.next;
        $('#pager').hidden = !(data.next || data.previous);
      } catch (err) { rows.innerHTML = `<tr><td colspan="6" class="empty">${esc(err.message)}</td></tr>`; }
    }

    const rowHtml = (p) => `<tr><td><b>${esc(p.name)}</b></td><td>${esc(p.brand || '—')}</td>
      <td>${esc(p.gtin || '—')}</td><td>${esc(p.category || '—')}</td><td>${esc(p.net_quantity || '—')}</td>
      <td><div class="actions" style="justify-content:flex-start"><a class="btn secondary small" href="/products/${p.id}/">View</a><button class="btn secondary small" type="button" data-edit="${p.id}">Edit</button></div></td></tr>`;

    function setCategory(value) {
      const sel = form.elements.category;
      if (value && ![...sel.options].some((o) => o.value === value)) sel.add(new Option(value, value));
      sel.value = value || 'Dairy';
    }
    function openForm(product) {
      clearErrors(form);
      editing = product ? product.id : null;
      FIELDS.forEach((f) => { if (f !== 'category') form.elements[f].value = product ? (product[f] ?? '') : ''; });
      setCategory(product ? product.category : 'Dairy');
      card.hidden = false;
      form.elements.name.focus();
    }
    function closeForm() { card.hidden = true; editing = null; clearErrors(form); }

    $('#add-product').addEventListener('click', (e) => { e.preventDefault(); openForm(null); });
    $('#entry-cancel').addEventListener('click', closeForm);
    rows.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-edit]');
      if (!b) return;
      try { openForm(await api(`/api/products/${b.dataset.edit}/`)); window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (err) { toast(err.message, 'error'); }
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(form);
      const body = {};
      FIELDS.forEach((f) => { body[f] = form.elements[f].value.trim(); });
      const btn = $('button[type=submit]', form);
      busy(btn, true, 'Saving…');
      try {
        await api(editing ? `/api/products/${editing}/` : '/api/products/', { method: editing ? 'PUT' : 'POST', body });
        toast(editing ? 'Product updated.' : 'Product added.', 'success');
        closeForm(); state.page = 1; load();
      } catch (err) { showErrors(form, err); }
      busy(btn, false);
    });

    $('#f-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { state.page = 1; load(); }, 300); });
    $('#f-category').addEventListener('change', () => { state.page = 1; load(); });
    $('#prev').addEventListener('click', () => { state.page -= 1; load(); });
    $('#next').addEventListener('click', () => { state.page += 1; load(); });
    load();

    if (card.dataset.mode === 'add') openForm(null);
    if (card.dataset.mode === 'edit') api(`/api/products/${card.dataset.id}/`).then(openForm).catch((err) => toast(err.message, 'error'));
  }

  /* ---------- Details ---------- */
  async function initDetail(box) {
    try {
      const p = await api(`/api/products/${box.dataset.id}/`);
      const row = (label, value) => `<dt>${label}</dt><dd>${value ? esc(value) : '—'}</dd>`;
      box.innerHTML = `<div class="profile-head"><div class="avatar lg">📦</div>
          <div style="flex:1"><h2>${esc(p.name)}</h2></div>
          <a class="btn" href="/products/${p.id}/edit/">Edit</a></div>
        <dl class="dl">${row('Brand', p.brand)}${row('Barcode', p.gtin)}${row('Category', p.category)}${row('Net quantity', p.net_quantity)}
          ${row('Manufacturer', p.manufacturer)}${row('Added by', p.created_by_name)}
          <dt>Last updated</dt><dd>${esc(LIP.fmtDate(p.updated_at))}</dd></dl>`;
    } catch (err) { box.innerHTML = `<div class="empty">${esc(err.status === 404 ? 'Product not found.' : err.message)}</div>`; }
  }

  if ($('#product-rows')) initList();
  if ($('#product-detail')) initDetail($('#product-detail'));
})();
