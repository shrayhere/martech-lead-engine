(function () {
  const { get, qs, esc, fmtNum, $, categoryBadge, scoreBar, initials, loadingHTML, errorHTML, emptyHTML } = App;
  const ICONS = {
    contacts: ['#eff4ff', '#2563eb', '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'],
    companies: ['#f0f9ff', '#0284c7', '<path d="M3 21h18"/><path d="M5 21V7l7-4v18"/><path d="M19 21V11l-7-4"/>'],
    leads: ['#f5f3ff', '#7c3aed', '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>'],
    hot: ['#fef2f2', '#dc2626', '<path d="M12 2c1 3 4 5 4 9a4 4 0 0 1-8 0c0-2 1-3 1-3s-2 0-2 4a5 5 0 0 0 10 0c0-5-5-7-5-10z"/>'],
    warm: ['#fffbeb', '#d97706', '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2"/>'],
    cold: ['#f1f5f9', '#475569', '<path d="M12 2v20M4 7l16 10M20 7L4 17"/>'],
    month: ['#ecfdf5', '#059669', '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>'],
    imports: ['#eff4ff', '#2563eb', '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>'],
  };
  const tile = (key, lbl, value, sub, href) => {
    const [bg, fg, path] = ICONS[key];
    return `<div class="card stat ${href ? "clickable" : ""}" ${href ? `onclick="location.href='${href}'"` : ""}>
      <div class="label"><span class="chip" style="background:${bg};color:${fg}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${path}</svg></span>${lbl}</div>
      <div class="value">${fmtNum(value)}</div><div class="sub">${sub}</div></div>`;
  };

  async function load(range) {
    $("#stats").innerHTML = Array(8).fill(`<div class="card stat"><div class="skeleton" style="width:60%"></div><div class="skeleton" style="height:26px;width:40%"></div></div>`).join("");
    const q = qs(range);
    try {
      const [{ stats: s }, charts] = await Promise.all([get("/api/dashboard/stats" + q), get("/api/dashboard/charts" + q)]);
      const pct = (n) => (s.total_leads ? Math.round(n / s.total_leads * 100) + "% of leads" : "—");
      $("#stats").innerHTML = [
        tile("contacts", "Total contacts", s.total_contacts, "In selected period", "/contacts"),
        tile("companies", "Total companies", s.total_companies, "In selected period", "/companies"),
        tile("leads", "Total leads", s.total_leads, `Avg. score ${s.average_lead_score}`, "/leads"),
        tile("hot", "Hot leads", s.hot_leads, pct(s.hot_leads), "/leads?category=hot"),
        tile("warm", "Warm leads", s.warm_leads, pct(s.warm_leads), "/leads?category=warm"),
        tile("cold", "Cold leads", s.cold_leads, pct(s.cold_leads), "/leads?category=cold"),
        tile("month", "New contacts this month", s.new_contacts_this_month, "Calendar month to date", "/contacts?sort=created"),
        tile("imports", "CSV imports completed", s.imports_completed, "In selected period", "/imports"),
      ].join("");
      Analytics.leadsOverTime("chart-leads-time", charts);
      $("#lot-sub").textContent = `New leads per ${charts.range.granularity} by creation date`;
      Analytics.distribution("chart-dist", charts.lead_distribution);
      Analytics.byCompany("chart-company", charts.contacts_by_company);
      $("#no-company-note").textContent = charts.contacts_by_company.without_company
        ? `${charts.contacts_by_company.without_company} contact(s) have no company.` : "";
      Analytics.sources("chart-sources", charts.lead_sources);
      Analytics.funnel("chart-funnel", charts.funnel);
      Analytics.imports("chart-imports", charts);
    } catch (e) { $("#stats").innerHTML = `<div class="card" style="grid-column:1/-1">${errorHTML(e.message)}</div>`; }
  }

  async function loadTop() {
    const box = $("#top-leads"); box.innerHTML = loadingHTML;
    try {
      const r = await get("/api/dashboard/recent");
      box.innerHTML = r.top_leads.length ? `<div class="table-wrap"><table class="table"><tbody>${r.top_leads.map((c) => `<tr style="cursor:pointer" onclick="location.href='/contacts/${c.contact_id}'">
          <td><div class="cell-main" style="min-width:0"><span class="avatar sm">${esc(initials(c.full_name))}</span><div><div class="t">${esc(c.full_name)}</div><div class="s">${esc(c.company?.company_name || c.job_title || "")}</div></div></div></td>
          <td>${categoryBadge(c)}</td><td>${scoreBar(c.lead_score, c.lead_category)}</td></tr>`).join("")}</tbody></table></div>`
        : emptyHTML("No leads yet", "Create contacts or import a CSV to start scoring leads.", `<a class="btn primary sm" href="/imports">Import CSV</a>`);
    } catch (e) { box.innerHTML = errorHTML(e.message); }
  }

  Analytics.rangePicker(load);
  load({ range: "all" });
  loadTop();
})();
