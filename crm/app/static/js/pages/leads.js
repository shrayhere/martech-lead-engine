(function () {
  const { get, api, qs, esc, $, $$, fmtRelative, initials, label, toast, loadingHTML, errorHTML, debounce, download, CAT_COLORS } = App;
  const params = new URLSearchParams(location.search);
  let table = null, tableCat = params.get("category") || "";
  let view = params.get("category") || params.get("overridden") ? "table" : "pipeline";

  async function loadStats() {
    try {
      const a = await get("/api/leads/analytics");
      const d = a.distribution, best = [...a.by_source].sort((x, y) => y.average_score - x.average_score)[0];
      $("#lead-stats").innerHTML = `
        <div class="card stat"><div class="label">Total leads</div><div class="value">${a.total_leads}</div><div class="sub">${a.excluded} excluded (invalid contact info)</div></div>
        <div class="card stat"><div class="label">Hot · Warm · Cold</div><div class="value"><span style="color:${CAT_COLORS.hot}">${d.hot}</span> · <span style="color:${CAT_COLORS.warm}">${d.warm}</span> · <span style="color:${CAT_COLORS.cold}">${d.cold}</span></div><div class="sub">Effective categories (incl. overrides)</div></div>
        <div class="card stat"><div class="label">Manual overrides</div><div class="value">${a.manual_overrides}</div><div class="sub"><a href="/leads?overridden=1">View overridden leads</a></div></div>
        <div class="card stat"><div class="label">Best source by avg. score</div><div class="value" style="font-size:20px">${esc(best?.source || "—")}</div><div class="sub">${best ? `avg ${best.average_score} · ${best.leads} leads` : "No leads yet"}</div></div>`;
    } catch (e) { $("#lead-stats").innerHTML = `<div class="card" style="grid-column:1/-1">${errorHTML(e.message)}</div>`; }
  }

  // ---------------------------------------------------------------- Kanban
  const COLS = [["hot", "🔥 Hot", "60–100"], ["warm", "Warm", "30–59"], ["cold", "Cold", "0–29"]];
  let kq = "";
  async function loadPipeline() {
    const board = $("#kanban");
    board.innerHTML = COLS.map(([k, l, r]) => `<div class="k-col" data-col="${k}"><div class="k-head"><div><span class="badge ${k}">${l}</span> <span class="small muted">score ${r}</span></div><strong class="k-count">…</strong></div><div class="k-list">${loadingHTML}</div></div>`).join("");
    try {
      const { columns } = await get("/api/leads/pipeline" + qs({ q: kq, limit: 40 }));
      COLS.forEach(([k]) => {
        const col = $(`[data-col="${k}"]`, board), info = columns[k];
        $(".k-count", col).textContent = info.total;
        $(".k-list", col).innerHTML = info.items.length ? info.items.map(card).join("")
          + (info.total > info.items.length ? `<div class="k-more">Showing top ${info.items.length} of ${info.total} · <a href="/leads?category=${k}">see all</a></div>` : "")
          : `<div class="k-more" style="padding:30px 6px">No ${k} leads${kq ? " match this filter" : ""}.<br>Drop a card here to move it.</div>`;
      });
      bindDrag();
    } catch (e) { board.innerHTML = `<div class="card" style="grid-column:1/-1">${errorHTML(e.message)}</div>`; }
  }
  function card(c) {
    return `<div class="k-card" draggable="true" data-id="${c.contact_id}" data-auto="${c.lead_category_auto}" data-cat="${c.lead_category}">
      <div class="k-top"><div style="min-width:0"><a class="k-name" href="/contacts/${c.contact_id}" draggable="false">${esc(c.full_name)}</a>
        <div class="k-sub">${esc([c.job_title, c.company?.company_name].filter(Boolean).join(" · ") || c.email || "")}</div></div>
        <span class="badge ${c.lead_category} plain">${c.lead_score}</span></div>
      <div class="k-foot"><span>${c.last_activity_at ? "Active " + fmtRelative(c.last_activity_at) : "No activity"}</span>
        ${c.lead_category_override ? `<span title="Automatic: ${label(c.lead_category_auto)}">✎ override</span>` : `<span>${esc(c.lead_source || "")}</span>`}</div></div>`;
  }
  function bindDrag() {
    $$(".k-card").forEach((el) => {
      el.addEventListener("dragstart", (e) => { el.classList.add("dragging"); e.dataTransfer.setData("text/plain", el.dataset.id); e.dataTransfer.effectAllowed = "move"; });
      el.addEventListener("dragend", () => el.classList.remove("dragging"));
    });
    $$(".k-col").forEach((col) => {
      col.addEventListener("dragover", (e) => { e.preventDefault(); col.classList.add("drag-over"); });
      col.addEventListener("dragleave", (e) => { if (!col.contains(e.relatedTarget)) col.classList.remove("drag-over"); });
      col.addEventListener("drop", async (e) => {
        e.preventDefault(); col.classList.remove("drag-over");
        const id = e.dataTransfer.getData("text/plain"), cardEl = $(`.k-card[data-id="${id}"]`);
        const target = col.dataset.col;
        if (!cardEl || cardEl.dataset.cat === target) return;
        $(".k-list", col).prepend(cardEl);  // optimistic move
        try {
          const { contact } = await api("PUT", `/api/leads/${id}/category`, { category: target, reason: "Moved on pipeline board" });
          toast(contact.lead_category_override ? `${contact.full_name} moved to ${label(target)} (manual override; automatic is ${label(contact.lead_category_auto)}).`
            : `${contact.full_name} is back on its automatic category (${label(target)}).`);
        } catch (err) { toast(err.message, "error"); }
        loadPipeline(); loadStats();
      });
    });
  }
  $("#k-q").addEventListener("input", debounce(() => { kq = $("#k-q").value.trim(); loadPipeline(); }, 300));

  // ---------------------------------------------------------------- table
  function buildTable() {
    table = ContactTable($("#lead-table"), { endpoint: "/api/leads", leadsOnly: true, fixed: { category: tableCat } });
  }
  $("#cat-tabs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-cat]"); if (!b) return;
    $$("#cat-tabs button").forEach((x) => x.classList.toggle("active", x === b));
    tableCat = b.dataset.cat; buildTable();
  });

  function setView(v) {
    view = v;
    $$("#view-toggle button").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
    $("#pipeline-view").classList.toggle("hidden", v !== "pipeline");
    $("#table-view").classList.toggle("hidden", v !== "table");
    if (v === "pipeline") loadPipeline();
    else if (!table) {
      $$("#cat-tabs button").forEach((x) => x.classList.toggle("active", x.dataset.cat === tableCat));
      buildTable();
    }
  }
  $("#view-toggle").addEventListener("click", (e) => { const b = e.target.closest("[data-view]"); if (b) setView(b.dataset.view); });
  $("#export-btn").onclick = () => (table && view === "table" ? table.exportCsv() : download("/api/contacts/export" + qs({ leads_only: 1 })));

  loadStats();
  setView(view);
})();
