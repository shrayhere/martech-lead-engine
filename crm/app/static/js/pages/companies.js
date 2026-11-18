(function () {
  const { get, api, qs, esc, $, fmtDate, fmtRelative, initials, toast, confirmDialog, renderPagination, bindSort,
    loadingHTML, emptyHTML, errorHTML, debounce, download, companyForm, CAT_COLORS } = App;
  const params = new URLSearchParams(location.search);
  const state = { page: 1, per_page: 25, sort: "name", order: "asc", q: params.get("q") || "", industry: "", country: "",
    has_contacts: params.get("has_contacts") || "" };
  let last;
  $("#q").value = state.q; $("#has").value = state.has_contacts;

  get("/api/companies/facets").then((f) => {
    $("#industry").innerHTML += f.industries.map((i) => `<option>${esc(i)}</option>`).join("");
    $("#country").innerHTML += f.countries.map((i) => `<option>${esc(i)}</option>`).join("");
  }).catch(() => {});

  const mix = (d, total) => {
    const sum = d.hot + d.warm + d.cold;
    if (!sum) return '<span class="muted small">No leads</span>';
    const seg = (n, color) => (n ? `<span style="width:${n / sum * 100}%;background:${color}" title="${n}"></span>` : "");
    return `<div style="display:flex;align-items:center;gap:8px"><div class="dist-bar" style="width:110px">${seg(d.hot, CAT_COLORS.hot)}${seg(d.warm, CAT_COLORS.warm)}${seg(d.cold, "#94a3b8")}</div>
      <span class="small muted nowrap">${d.hot} · ${d.warm} · ${d.cold}</span></div>`;
  };

  async function load() {
    const body = $("#body"); body.innerHTML = `<tr><td colspan="8">${loadingHTML}</td></tr>`;
    try {
      last = await get("/api/companies" + qs(state));
      body.innerHTML = last.items.length ? last.items.map((c) => `<tr>
        <td><div class="cell-main"><span class="avatar sm company">${esc(initials(c.company_name))}</span><div>
          <a class="t" href="/companies/${c.company_id}">${esc(c.company_name)}</a><div class="s">${esc((c.website || "").replace("https://", ""))}</div></div></div></td>
        <td>${esc(c.industry || "—")}</td><td class="hide-sm">${esc([c.city, c.country].filter(Boolean).join(", ") || "—")}</td>
        <td><a href="/contacts?company_id=${c.company_id}"><strong>${c.contact_count}</strong></a> <span class="muted small">(${c.lead_count} leads)</span></td>
        <td>${mix(c.distribution)}</td>
        <td class="hide-sm nowrap">${c.last_activity_at ? fmtRelative(c.last_activity_at) : '<span class="muted">—</span>'}</td>
        <td class="hide-sm nowrap">${fmtDate(c.created_at)}</td>
        <td class="actions"><a class="btn sm ghost" href="/companies/${c.company_id}">View</a>
          <button class="btn sm ghost" data-edit="${c.company_id}">Edit</button>
          <button class="btn sm ghost" data-del="${c.company_id}" aria-label="Delete ${esc(c.company_name)}">🗑</button></td></tr>`).join("")
        : `<tr><td colspan="8">${emptyHTML("No companies found", "Create a company, or import a CSV with a company column.", `<button class="btn primary sm" data-add>New company</button>`)}</td></tr>`;
      body.querySelector("[data-add]")?.addEventListener("click", () => companyForm(null));
      renderPagination($("#pages"), last, (p) => { state.page = p; load(); });
    } catch (e) { body.innerHTML = `<tr><td colspan="8">${errorHTML(e.message)}</td></tr>`; }
  }

  $("#body").addEventListener("click", async (e) => {
    const ed = e.target.closest("[data-edit]"), del = e.target.closest("[data-del]");
    if (ed) companyForm(last.items.find((c) => c.company_id === +ed.dataset.edit), { onSaved: load });
    if (del) {
      const c = last.items.find((x) => x.company_id === +del.dataset.del);
      const msg = c.contact_count
        ? `Delete <strong>${esc(c.company_name)}</strong>? Its <strong>${c.contact_count}</strong> contact(s) will be kept but no longer associated with any company.`
        : `Delete <strong>${esc(c.company_name)}</strong>? This cannot be undone.`;
      if (!(await confirmDialog(msg, { confirmLabel: "Delete company" }))) return;
      try { const r = await api("DELETE", `/api/companies/${c.company_id}`); toast(`Company deleted. ${r.contacts_unassigned} contact(s) unassigned.`); load(); }
      catch (err) { toast(err.message, "error"); }
    }
  });
  const reload = () => { state.page = 1; load(); };
  $("#q").addEventListener("input", debounce(() => { state.q = $("#q").value.trim(); reload(); }, 300));
  $("#industry").addEventListener("change", (e) => { state.industry = e.target.value; reload(); });
  $("#country").addEventListener("change", (e) => { state.country = e.target.value; reload(); });
  $("#has").addEventListener("change", (e) => { state.has_contacts = e.target.value; reload(); });
  bindSort($("#table"), state, reload);
  $("#add-btn").onclick = () => companyForm(null);
  $("#export-btn").onclick = () => { const f = { ...state }; delete f.page; delete f.per_page; download("/api/companies/export" + qs(f)); };
  load();
})();
