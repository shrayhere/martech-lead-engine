/* Server-paginated, filterable, sortable, bulk-selectable contact/lead table (used by Contacts and Leads). */
(function () {
  const { get, api, qs, esc, $, $$, fmtDate, fmtRelative, categoryBadge, scoreBar, initials, stageLabel, label, toast,
    confirmDialog, renderPagination, bindSort, loadingHTML, emptyHTML, errorHTML, debounce, download, contactForm, LIFECYCLE } = App;

  function ContactTable(root, { endpoint = "/api/contacts", exportUrl = "/api/contacts/export", leadsOnly = false, fixed = {} } = {}) {
    const params = new URLSearchParams(location.search);
    const state = {
      page: 1, per_page: 25, sort: params.get("sort") || (leadsOnly ? "score" : "created"),
      order: params.get("order") || "desc",
      q: params.get("q") || "", category: params.get("category") || "", company_id: params.get("company_id") || "",
      company_name: "", no_company: params.get("no_company") || "", lifecycle_stage: params.get("lifecycle_stage") || "",
      lead_source: params.get("lead_source") || "", score_min: params.get("score_min") || "",
      created_from: "", created_to: "", inactive_days: params.get("inactive_days") || "",
      overridden: params.get("overridden") || "", source_id: params.get("source_id") || "",
      leads_only: params.get("leads_only") || "", ...fixed,
    };
    const selected = new Set();
    let lastData = null;

    root.innerHTML = `
      <div class="toolbar">
        <input class="input grow" type="search" id="t-q" placeholder="Search name, email, phone or company…" value="${esc(state.q)}">
        ${"category" in fixed ? "" : `<select class="input" id="t-category" style="width:auto"><option value="">All categories</option>
          <option value="hot">🔥 Hot</option><option value="warm">Warm</option><option value="cold">Cold</option><option value="excluded">Excluded</option></select>`}
        <div class="combo" style="width:220px" id="t-company"></div>
        <select class="input" id="t-stage" style="width:auto"><option value="">All lifecycle stages</option>${LIFECYCLE.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
        <button class="btn sm" id="t-more">More filters</button>
        <button class="btn sm ghost" id="t-reset">Reset</button>
      </div>
      <div class="toolbar hidden" id="t-more-row">
        <div class="field"><label>Lead source</label><select class="input sm" id="t-source"><option value="">Any source</option></select></div>
        <div class="field"><label>Minimum score</label><select class="input sm" id="t-score"><option value="">Any</option><option value="30">30+</option><option value="60">60+</option><option value="80">80+</option></select></div>
        <div class="field"><label>Created from</label><input class="input sm" type="date" id="t-from"></div>
        <div class="field"><label>Created to</label><input class="input sm" type="date" id="t-to"></div>
        <div class="field"><label>Last activity</label><select class="input sm" id="t-inactive"><option value="">Any time</option><option value="30">No activity in 30 days</option><option value="90">No activity in 90 days</option></select></div>
      </div>
      <div class="bulk-bar hidden" id="t-bulk">
        <strong id="t-bulk-count"></strong>
        <select class="input sm" id="t-bulk-cat" style="width:auto"><option value="">Set category…</option><option value="hot">Hot</option><option value="warm">Warm</option><option value="cold">Cold</option><option value="__clear">Reset to automatic</option></select>
        <select class="input sm" id="t-bulk-stage" style="width:auto"><option value="">Set lifecycle…</option>${LIFECYCLE.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
        <button class="btn sm danger" id="t-bulk-delete">Delete selected</button>
        <button class="btn sm ghost" id="t-bulk-clear">Clear selection</button>
      </div>
      <div class="table-wrap"><table class="table" id="t-table"><thead><tr>
        <th class="cb"><input type="checkbox" id="t-all" aria-label="Select all on page"></th>
        <th data-sort="name">Name</th><th data-sort="company">Company</th><th>Category</th>
        <th data-sort="score" data-default="desc">Score</th><th class="hide-sm">Lifecycle</th><th class="hide-sm">Source</th>
        <th data-sort="last_activity" data-default="desc">Last activity</th><th data-sort="created" data-default="desc" class="hide-sm">Created</th><th></th>
      </tr></thead><tbody id="t-body"></tbody></table></div>
      <div class="pagination" id="t-pages"></div>`;

    // initial control values
    if ($("#t-category", root)) $("#t-category", root).value = state.category;
    $("#t-stage", root).value = state.lifecycle_stage;
    $("#t-inactive", root).value = state.inactive_days;
    $("#t-score", root).value = state.score_min;
    if (state.inactive_days || state.lead_source || state.score_min) $("#t-more-row", root).classList.remove("hidden");

    get("/api/leads/sources").then(({ items }) => {
      $("#t-source", root).innerHTML += items.map((s) => `<option ${s === state.lead_source ? "selected" : ""}>${esc(s)}</option>`).join("");
    }).catch(() => {});

    // company filter combo
    const comboBox = $("#t-company", root);
    function renderCompanyFilter() {
      if (state.company_id || state.no_company) {
        const name = state.no_company ? "No company" : (state.company_name || `Company #${state.company_id}`);
        comboBox.innerHTML = `<div class="selected-chip" style="padding:6px 10px"><span class="small">🏢 ${esc(name)}</span><button class="link-btn small" id="t-co-clear">✕</button></div>`;
        $("#t-co-clear", comboBox).onclick = () => { state.company_id = ""; state.no_company = ""; state.company_name = ""; renderCompanyFilter(); reload(); };
        return;
      }
      comboBox.innerHTML = `<input class="input" placeholder="Filter by company…" autocomplete="off"><div class="dropdown hidden"></div>`;
      const input = $("input", comboBox), dd = $(".dropdown", comboBox);
      const search = debounce(async () => {
        const { items } = await get("/api/companies/options" + qs({ q: input.value.trim() }));
        dd.innerHTML = `<button class="item" data-none>∅ Contacts without a company</button><div class="sep"></div>`
          + items.map((c) => `<button class="item" data-id="${c.company_id}" data-name="${esc(c.company_name)}">${esc(c.company_name)}</button>`).join("");
        dd.classList.remove("hidden");
        $("[data-none]", dd).onclick = () => { state.no_company = "1"; renderCompanyFilter(); reload(); };
        $$("[data-id]", dd).forEach((b) => b.onclick = () => { state.company_id = b.dataset.id; state.company_name = b.dataset.name; renderCompanyFilter(); reload(); });
      }, 200);
      input.addEventListener("input", search); input.addEventListener("focus", search);
      input.addEventListener("blur", () => setTimeout(() => dd.classList.add("hidden"), 180));
    }
    if (state.company_id) get(`/api/companies/${state.company_id}`).then((r) => { state.company_name = r.company.company_name; renderCompanyFilter(); }).catch(() => {});
    renderCompanyFilter();

    const reload = () => { state.page = 1; load(); };
    $("#t-q", root).addEventListener("input", debounce(() => { state.q = $("#t-q", root).value.trim(); reload(); }, 300));
    $("#t-category", root)?.addEventListener("change", (e) => { state.category = e.target.value; reload(); });
    $("#t-stage", root).addEventListener("change", (e) => { state.lifecycle_stage = e.target.value; reload(); });
    $("#t-source", root).addEventListener("change", (e) => { state.lead_source = e.target.value; reload(); });
    $("#t-score", root).addEventListener("change", (e) => { state.score_min = e.target.value; reload(); });
    $("#t-from", root).addEventListener("change", (e) => { state.created_from = e.target.value; reload(); });
    $("#t-to", root).addEventListener("change", (e) => { state.created_to = e.target.value; reload(); });
    $("#t-inactive", root).addEventListener("change", (e) => { state.inactive_days = e.target.value; reload(); });
    $("#t-more", root).addEventListener("click", () => $("#t-more-row", root).classList.toggle("hidden"));
    $("#t-reset", root).addEventListener("click", () => {
      Object.assign(state, { q: "", category: fixed.category ?? "", company_id: "", company_name: "", no_company: "", lifecycle_stage: "",
        lead_source: "", score_min: "", created_from: "", created_to: "", inactive_days: "", overridden: "", source_id: "", leads_only: "" });
      root.querySelectorAll("input.input, select.input").forEach((el) => { if (!el.closest("#t-bulk")) el.value = ""; });
      history.replaceState(null, "", location.pathname);
      renderCompanyFilter(); reload();
    });
    bindSort($("#t-table", root), state, reload);

    function filters() {
      const f = { ...state }; delete f.company_name;
      if (leadsOnly) f.leads_only = 1;
      return f;
    }

    async function load() {
      const body = $("#t-body", root);
      body.innerHTML = `<tr><td colspan="10">${loadingHTML}</td></tr>`;
      try {
        const data = await get(endpoint + qs(filters()));
        lastData = data;
        if (!data.items.length) {
          body.innerHTML = `<tr><td colspan="10">${emptyHTML(leadsOnly ? "No leads match these filters" : "No contacts match these filters",
            "Try clearing filters, or add records manually or by CSV import.",
            `<div class="page-actions" style="justify-content:center"><button class="btn primary sm" data-add>Add contact</button><a class="btn sm" href="/imports">Import CSV</a></div>`)}</td></tr>`;
          $("[data-add]", body).onclick = () => contactForm(null);
        } else {
          body.innerHTML = data.items.map(row).join("");
        }
        renderPagination($("#t-pages", root), data, (p) => { state.page = p; load(); window.scrollTo({ top: 0, behavior: "smooth" }); });
        syncSelection();
      } catch (e) { body.innerHTML = `<tr><td colspan="10">${errorHTML(e.message)}</td></tr>`; }
    }

    function row(c) {
      return `<tr data-id="${c.contact_id}" class="${selected.has(c.contact_id) ? "selected" : ""}">
        <td class="cb"><input type="checkbox" data-select="${c.contact_id}" ${selected.has(c.contact_id) ? "checked" : ""} aria-label="Select ${esc(c.full_name)}"></td>
        <td><div class="cell-main"><span class="avatar sm">${esc(initials(c.full_name))}</span><div>
          <a class="t" href="/contacts/${c.contact_id}">${esc(c.full_name)}</a>
          <div class="s">${esc(c.email || c.phone || "No email or phone")}${c.job_title ? " · " + esc(c.job_title) : ""}</div></div></div></td>
        <td>${c.company ? `<a href="/companies/${c.company.company_id}">${esc(c.company.company_name)}</a>` : '<span class="muted">—</span>'}</td>
        <td>${categoryBadge(c)}</td>
        <td>${scoreBar(c.lead_score, c.lead_category)}</td>
        <td class="hide-sm"><span class="badge gray plain">${stageLabel(c.lifecycle_stage)}</span></td>
        <td class="hide-sm">${esc(c.lead_source || "—")}</td>
        <td class="nowrap" title="${fmtDate(c.last_activity_at, true)}">${c.last_activity_at ? fmtRelative(c.last_activity_at) : '<span class="muted">Never</span>'}</td>
        <td class="nowrap hide-sm">${fmtDate(c.created_at)}</td>
        <td class="actions"><a class="btn sm ghost" href="/contacts/${c.contact_id}">View</a>
          <button class="btn sm ghost" data-edit="${c.contact_id}">Edit</button>
          <button class="btn sm ghost" data-del="${c.contact_id}" title="Delete" aria-label="Delete ${esc(c.full_name)}">🗑</button></td></tr>`;
    }

    // row actions (delegated)
    $("#t-body", root).addEventListener("click", async (e) => {
      const edit = e.target.closest("[data-edit]"), del = e.target.closest("[data-del]");
      if (edit) {
        const c = lastData.items.find((i) => i.contact_id === +edit.dataset.edit);
        contactForm(c, { onSaved: () => load() });
      } else if (del) {
        const c = lastData.items.find((i) => i.contact_id === +del.dataset.del);
        if (!(await confirmDialog(`Delete <strong>${esc(c.full_name)}</strong> and their activity history? This cannot be undone.`, { confirmLabel: "Delete contact" }))) return;
        try { await api("DELETE", `/api/contacts/${c.contact_id}`); selected.delete(c.contact_id); toast("Contact deleted."); load(); }
        catch (err) { toast(err.message, "error"); }
      }
    });
    $("#t-body", root).addEventListener("change", (e) => {
      const cb = e.target.closest("[data-select]"); if (!cb) return;
      const id = +cb.dataset.select;
      cb.checked ? selected.add(id) : selected.delete(id);
      cb.closest("tr").classList.toggle("selected", cb.checked);
      syncSelection();
    });
    $("#t-all", root).addEventListener("change", (e) => {
      (lastData?.items || []).forEach((c) => (e.target.checked ? selected.add(c.contact_id) : selected.delete(c.contact_id)));
      $$("[data-select]", root).forEach((cb) => { cb.checked = e.target.checked; cb.closest("tr").classList.toggle("selected", cb.checked); });
      syncSelection();
    });
    function syncSelection() {
      $("#t-bulk", root).classList.toggle("hidden", !selected.size);
      $("#t-bulk-count", root).textContent = `${selected.size} selected`;
      const ids = (lastData?.items || []).map((c) => c.contact_id);
      $("#t-all", root).checked = ids.length > 0 && ids.every((id) => selected.has(id));
    }
    async function bulk(action, value, confirmMsg) {
      if (confirmMsg && !(await confirmDialog(confirmMsg, { confirmLabel: action === "delete" ? "Delete" : "Apply", danger: action === "delete" }))) return;
      try {
        const r = await api("POST", "/api/contacts/bulk", { ids: [...selected], action, value });
        toast(r.message); if (action === "delete") selected.clear(); load();
      } catch (e) { toast(e.message, "error"); }
    }
    $("#t-bulk-cat", root).addEventListener("change", (e) => {
      const v = e.target.value; e.target.value = ""; if (!v) return;
      if (v === "__clear") bulk("clear_override", null);
      else bulk("set_category", v, `Manually set <strong>${selected.size}</strong> lead(s) to <strong>${label(v)}</strong>? The automatic category is kept and each change is recorded in the audit log. Contacts excluded for invalid details are skipped.`);
    });
    $("#t-bulk-stage", root).addEventListener("change", (e) => { const v = e.target.value; e.target.value = ""; if (v) bulk("set_lifecycle", v); });
    $("#t-bulk-delete", root).addEventListener("click", () => bulk("delete", null, `Permanently delete <strong>${selected.size}</strong> contact(s) and their activities? This cannot be undone.`));
    $("#t-bulk-clear", root).addEventListener("click", () => { selected.clear(); $$("[data-select]", root).forEach((cb) => { cb.checked = false; cb.closest("tr").classList.remove("selected"); }); syncSelection(); });

    load();
    return { reload: load, exportCsv: () => { const f = filters(); delete f.page; delete f.per_page; download(exportUrl + qs(f)); } };
  }
  window.ContactTable = ContactTable;
})();
