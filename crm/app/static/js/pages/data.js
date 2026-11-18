(function () {
  const { get, api, qs, esc, $, $$, fmtDate, fmtNum, label, toast, confirmDialog, renderPagination, loadingHTML, emptyHTML, errorHTML } = App;

  async function loadQuality() {
    const box = $("#quality"); box.innerHTML = `<div class="card">${loadingHTML}</div>`.repeat(3);
    try {
      const q = await get("/api/data-quality");
      box.innerHTML = `
        <div class="card"><div class="card-head"><div><h3>Data quality checks</h3><p>${fmtNum(q.total_contacts)} contacts</p></div></div><div class="card-body">
          ${q.checks.map((c) => `<div class="quality-item"><span>${c.count ? "⚠" : "✅"} ${esc(c.label)}</span>
            ${c.link && c.count ? `<a class="badge ${c.count ? "amber" : "green"} plain" href="${c.link}">${fmtNum(c.count)} →</a>` : `<span class="badge ${c.count ? "amber" : "green"} plain">${fmtNum(c.count)}</span>`}</div>`).join("")}
          <div class="quality-item"><span>${q.pending_duplicates ? "⚠" : "✅"} Possible duplicates awaiting review</span><span class="badge ${q.pending_duplicates ? "amber" : "green"} plain">${q.pending_duplicates}</span></div>
        </div></div>
        <div class="card"><div class="card-head"><div><h3>Field completeness</h3><p>Share of contacts with each field filled</p></div></div><div class="card-body">
          ${Object.entries(q.completeness).map(([k, v]) => `<div class="mb"><div style="display:flex;justify-content:space-between" class="small"><span>${label(k)}</span><strong>${v}%</strong></div>
            <div class="progress mt" style="margin-top:4px"><span style="width:${v}%;background:${v > 80 ? "var(--success)" : v > 50 ? "var(--primary)" : "var(--warm)"}"></span></div></div>`).join("")}
        </div></div>
        <div class="card"><div class="card-head"><div><h3>Data sources</h3><p>Where records came from (many-to-many)</p></div></div><div class="card-body flush table-wrap">
          <table class="table"><thead><tr><th>Source</th><th>Type</th><th>Contacts</th></tr></thead><tbody>
          ${q.sources.map((s) => `<tr><td><strong>${esc(s.source_name)}</strong></td>
            <td><span class="badge ${s.source_type === "seed" ? "amber" : s.source_type === "csv" ? "blue" : "gray"} plain">${label(s.source_type)}</span></td>
            <td><a href="/contacts?source_id=${s.source_id}">${fmtNum(s.contacts)}</a></td></tr>`).join("")}</tbody></table></div></div>`;
    } catch (e) { box.innerHTML = `<div class="card">${errorHTML(e.message)}</div>`; }
  }

  // ---------------------------------------------------------------- duplicates
  let dStatus = "pending", dPage = 1, dData;
  const FIELD_LABELS = { first_name: "First name", last_name: "Last name", email: "Email", phone: "Phone", job_title: "Job title",
    lead_source: "Lead source", lifecycle_stage: "Lifecycle stage", company: "Company" };
  const STATUS_TXT = { same: "", fills_blank: "adds missing value", missing_incoming: "incoming empty — kept", conflict: "conflict" };
  const RESOLVED = { kept_existing: "Kept existing", updated_existing: "Updated existing", merged: "Merged", not_duplicate: "Not a duplicate" };
  const ACTIONS = {
    keep_existing: ["Keep existing", "Discard the incoming record; the existing contact is unchanged."],
    update_existing: ["Update existing", "Overwrite the existing contact with the incoming non-empty values."],
    merge: ["Merge records", "Keep existing values and fill in only the fields that are empty."],
    not_duplicate: ["Not a duplicate", "Keep both as separate contacts."],
  };

  function dupCard(d) {
    const e = d.existing, inc = d.incoming, pending = d.resolution_status === "pending";
    const incomingTitle = d.duplicate_contact_id ? `Stored contact <a href="/contacts/${d.duplicate_contact_id}">#${d.duplicate_contact_id}</a>`
      : d.import_id ? `Incoming CSV row ${inc.row_number ?? ""} (import <a href="/imports?report=${d.import_id}">#${d.import_id}</a>)` : "Removed contact (merged)";
    return `<div class="dup-card" data-id="${d.duplicate_id}">
      <div class="dup-head"><div><strong>${esc(d.matching_reason)}</strong> <span class="badge ${d.confidence_score >= .9 ? "red" : "amber"} plain">${Math.round(d.confidence_score * 100)}% confidence</span>
        <div class="small muted">Detected ${fmtDate(d.detected_at, true)}</div></div>
        ${pending ? `<div class="small"><span class="muted">Recommended:</span> <strong>${ACTIONS[d.recommended_action][0]}</strong> <span class="muted">— ${esc(d.recommendation_reason)}</span></div>`
          : `<span class="badge green">${RESOLVED[d.resolution_status]}${d.resolved_at ? " · " + fmtDate(d.resolved_at) : ""}</span>`}</div>
      <div class="table-wrap"><table class="table diff-table"><thead><tr><th>Field</th><th>Existing: <a href="/contacts/${e.contact_id}">${esc(e.full_name)}</a></th><th>${incomingTitle}</th><th></th></tr></thead><tbody>
        ${d.differences.map((f) => `<tr><td class="small muted">${FIELD_LABELS[f.field] || f.field}</td><td>${esc(f.existing ?? "—")}</td>
          <td class="${f.status}">${esc(f.incoming ?? "—")}</td><td class="small muted">${STATUS_TXT[f.status]}</td></tr>`).join("")}
        ${inc.activity ? `<tr><td class="small muted">Activity</td><td>—</td><td class="fills_blank">${esc(label(inc.activity.activity_type))} · ${fmtDate(inc.activity.activity_date)}</td><td class="small muted">will be added on update/merge</td></tr>` : ""}
      </tbody></table></div>
      ${pending ? `<div class="dup-actions">${Object.entries(ACTIONS).map(([k, [l, t]]) => `<button class="btn sm ${k === d.recommended_action ? "primary" : ""}" data-act="${k}" title="${esc(t)}">${l}</button>`).join("")}</div>` : ""}
    </div>`;
  }

  async function loadDups() {
    const box = $("#dups"); box.innerHTML = loadingHTML;
    try {
      dData = await get("/api/duplicates" + qs({ status: dStatus, page: dPage, per_page: 10 }));
      box.innerHTML = dData.items.length ? dData.items.map(dupCard).join("")
        : emptyHTML(dStatus === "pending" ? "No duplicates to review" : "Nothing here", dStatus === "pending"
          ? "Duplicates found during CSV imports or by scanning your contacts will appear here." : "No duplicates with this status.",
          dStatus === "pending" ? `<button class="btn primary sm" id="scan-2">Scan existing contacts</button>` : "");
      $("#scan-2")?.addEventListener("click", scan);
      renderPagination($("#dup-pages"), dData, (p) => { dPage = p; loadDups(); });
    } catch (e) { box.innerHTML = errorHTML(e.message); }
  }
  $("#dups").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]"); if (!btn) return;
    const card = btn.closest("[data-id]"), d = dData.items.find((x) => x.duplicate_id === +card.dataset.id), act = btn.dataset.act;
    const removes = d.duplicate_contact_id && act !== "not_duplicate";
    const msg = `<strong>${ACTIONS[act][0]}</strong>: ${ACTIONS[act][1]}`
      + (removes ? `<br><br>The duplicate contact <strong>#${d.duplicate_contact_id}</strong> will be <strong>deleted</strong> after its activities are moved to <strong>${esc(d.existing.full_name)}</strong>. This cannot be undone.` : "");
    if (!(await confirmDialog(msg, { title: "Resolve duplicate", confirmLabel: ACTIONS[act][0], danger: removes || act === "update_existing" }))) return;
    try {
      const r = await api("POST", `/api/duplicates/${d.duplicate_id}/resolve`, { action: act });
      toast(`${ACTIONS[act][0]}: done.${r.result.created_contact_id ? " New contact created." : ""}`);
      loadDups(); loadQuality(); loadAudit(); App.refreshDupBadge();
    } catch (err) { toast(err.message, "error"); }
  });
  $("#dup-status").addEventListener("click", (e) => {
    const b = e.target.closest("[data-s]"); if (!b) return;
    $$("#dup-status button").forEach((x) => x.classList.toggle("active", x === b));
    dStatus = b.dataset.s; dPage = 1; loadDups();
  });
  async function scan() {
    const btn = $("#scan"); btn.disabled = true;
    try { const r = await api("POST", "/api/duplicates/scan"); toast(r.message, r.created ? "info" : "success"); loadDups(); loadQuality(); App.refreshDupBadge(); }
    catch (e) { toast(e.message, "error"); } finally { btn.disabled = false; }
  }
  $("#scan").onclick = scan;

  // ---------------------------------------------------------------- audit
  let aPage = 1, aType = "";
  const summarize = (a) => {
    const n = a.new_values || {}, o = a.old_values || {};
    const keys = Object.keys(n).length ? Object.keys(n) : Object.keys(o);
    return keys.slice(0, 4).map((k) => `<code>${esc(k)}</code> ${o[k] !== undefined && a.operation !== "delete" ? `${esc(String(o[k] ?? "—")).slice(0, 40)} → ` : ""}${esc(String(n[k] ?? (a.operation === "delete" ? o[k] : "—"))).slice(0, 60)}`).join("<br>")
      + (keys.length > 4 ? `<br><span class="muted">+${keys.length - 4} more</span>` : "");
  };
  async function loadAudit() {
    const body = $("#audit"); body.innerHTML = `<tr><td colspan="4">${loadingHTML}</td></tr>`;
    try {
      const data = await get("/api/activity-log" + qs({ page: aPage, per_page: 15, entity_type: aType }));
      body.innerHTML = data.items.length ? data.items.map((a) => `<tr><td class="nowrap small">${fmtDate(a.timestamp, true)}</td>
        <td>${a.entity_type === "contact" && a.operation !== "delete" && a.operation !== "delete_duplicate" ? `<a href="/contacts/${a.entity_id}">Contact #${a.entity_id}</a>`
          : a.entity_type === "company" && a.operation !== "delete" ? `<a href="/companies/${a.entity_id}">Company #${a.entity_id}</a>` : `${label(a.entity_type)}${a.entity_id ? " #" + a.entity_id : ""}`}</td>
        <td><span class="badge ${a.operation.includes("delete") ? "red" : a.operation === "create" ? "green" : "blue"} plain">${label(a.operation)}</span></td>
        <td class="small">${summarize(a)}</td></tr>`).join("") : `<tr><td colspan="4">${emptyHTML("No audit entries", "Changes you make will be recorded here.")}</td></tr>`;
      renderPagination($("#audit-pages"), data, (p) => { aPage = p; loadAudit(); });
    } catch (e) { body.innerHTML = `<tr><td colspan="4">${errorHTML(e.message)}</td></tr>`; }
  }
  $("#audit-type").addEventListener("change", (e) => { aType = e.target.value; aPage = 1; loadAudit(); });

  loadQuality(); loadDups(); loadAudit();
})();
