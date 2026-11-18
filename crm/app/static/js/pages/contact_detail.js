(function () {
  const { get, api, esc, $, $$, fmtDate, fmtRelative, fmtMoney, categoryBadge, initials, label, stageLabel, toast, confirmDialog,
    contactForm, activityForm, modal, errorHTML, emptyHTML, CAT_COLORS } = App;
  const id = window.CONTACT_ID;
  const root = $("#detail");
  let data;

  const OP_LABELS = { create: "Created", update: "Updated", delete: "Deleted", category_override: "Category changed manually",
    rescore: "Score recalculated", import_update: "Updated by CSV import", duplicate_merge: "Merged duplicate",
    duplicate_update_existing: "Updated from duplicate", duplicate_keep_existing: "Duplicate discarded",
    create_from_duplicate_review: "Created from duplicate review" };

  function changes(h) {
    const n = h.new_values || {}, o = h.old_values || {};
    if (h.operation === "category_override") return `${label(o.effective || o.lead_category_override || "auto")} → ${label(n.effective || n.lead_category_override || "automatic")}${n.reason ? ` · “${esc(n.reason)}”` : ""}`;
    const keys = Object.keys(n).filter((k) => !["auto", "auto_category"].includes(k)).slice(0, 4);
    return keys.map((k) => `<code>${esc(k)}</code>: ${esc(o[k] ?? "—")} → ${esc(n[k] ?? "—")}`).join(", ");
  }

  function render() {
    const c = data.contact, co = data.company, b = data.score_breakdown;
    document.title = `${c.full_name} · MarTech CRM`;
    $("#crumb").textContent = c.full_name;
    const catColor = CAT_COLORS[c.lead_category] || "#94a3b8";
    root.innerHTML = `
      <div class="card"><div class="profile-head">
        <span class="avatar lg">${esc(initials(c.full_name))}</span>
        <div style="flex:1;min-width:0">
          <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><h1>${esc(c.full_name)}</h1>${categoryBadge(c)}
            <span class="badge gray plain">${stageLabel(c.lifecycle_stage)}</span><span class="badge blue plain">${label(c.lead_status)}</span></div>
          <div class="meta">${c.job_title ? `<span>💼 ${esc(c.job_title)}</span>` : ""}
            ${co ? `<span>🏢 <a href="/companies/${co.company_id}">${esc(co.company_name)}</a></span>` : `<span class="muted">No company</span>`}
            ${c.email ? `<span>✉ <a href="mailto:${esc(c.email)}">${esc(c.email)}</a></span>` : ""}
            ${c.phone ? `<span>☎ <a href="tel:${esc(c.phone)}">${esc(c.phone)}</a></span>` : ""}</div>
        </div>
        <div class="page-actions">
          <button class="btn primary" id="log-act">+ Log activity</button>
          <button class="btn" id="edit">Edit</button>
          <button class="btn danger" id="delete">Delete</button>
        </div></div></div>
      ${data.pending_duplicates ? `<div class="card mt" style="padding:12px 16px;border-color:var(--warm-border);background:var(--warm-bg)">
        ⧉ This contact has <strong>${data.pending_duplicates}</strong> possible duplicate(s) waiting for review. <a href="/data">Review duplicates →</a></div>` : ""}
      <div class="grid grid-main mt">
        <div>
          <div class="card"><div class="card-head"><div><h3>Activity timeline</h3><p>${data.activity_count} activit${data.activity_count === 1 ? "y" : "ies"} · scores recalculate automatically</p></div></div>
            <div class="card-body">${data.activities.length ? `<ul class="timeline">${data.activities.map((a) => `
              <li><span class="tl-ico ${a.activity_score < 0 ? "neg" : ""}">${a.activity_score > 0 ? "+" : ""}${a.activity_score}</span>
                <div class="tl-body"><strong>${esc(a.activity_label)}</strong>
                  ${a.activity_description ? `<div class="small" style="color:var(--text-2)">${esc(a.activity_description)}</div>` : ""}
                  <div class="small muted" title="${fmtDate(a.activity_date, true)}">${fmtDate(a.activity_date, true)} · ${fmtRelative(a.activity_date)}</div></div>
                <div class="tl-actions"><button class="btn sm ghost" data-edit-act="${a.activity_id}">Edit</button>
                  <button class="btn sm ghost" data-del-act="${a.activity_id}" aria-label="Delete activity">🗑</button></div></li>`).join("")}</ul>`
              : emptyHTML("No activity yet", "Log demos, pricing questions, meetings or email engagement to score this lead.", `<button class="btn primary sm" id="log-act-2">Log first activity</button>`)}
            </div></div>
          <div class="card mt"><div class="card-head"><div><h3>Change history</h3><p>Audit log for this contact</p></div></div>
            <div class="card-body">${data.history.length ? `<ul class="timeline">${data.history.map((h) => `
              <li><span class="tl-ico" style="background:#f1f5f9;color:#475569">✎</span><div class="tl-body">
                <strong>${esc(OP_LABELS[h.operation] || label(h.operation))}</strong>
                <div class="small" style="color:var(--text-2)">${changes(h)}</div>
                <div class="small muted">${fmtDate(h.timestamp, true)}</div></div></li>`).join("")}</ul>` : `<p class="muted">No changes recorded.</p>`}</div></div>
        </div>
        <div>
          <div class="card"><div class="card-head"><h3>Lead score</h3>${categoryBadge(c)}</div>
            <div class="card-body">
              <div style="display:flex;align-items:flex-end;gap:10px"><span class="big-score" style="color:${catColor}">${c.lead_score}</span><span class="muted">/ 100</span></div>
              <div class="score" style="width:100%;margin-top:10px"><span class="bar"><span style="width:${Math.max(2, c.lead_score)}%;background:${catColor}"></span></span></div>
              <p class="small muted" style="margin:10px 0 0">${data.is_qualifiable
                ? `Automatic category: <strong>${label(c.lead_category_auto)}</strong>${c.lead_category_override ? ` · manually set to <strong>${label(c.lead_category_override)}</strong>` : ""}. Last engagement ${c.last_activity_at ? fmtRelative(c.last_activity_at) : "never"}.`
                : "Excluded from qualification: add a valid email or phone number."}</p>
              ${data.is_qualifiable ? `<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
                <select class="input sm" id="cat-select" style="width:auto">
                  <option value="">Automatic (${label(c.lead_category_auto)})</option>
                  ${["hot", "warm", "cold"].map((k) => `<option value="${k}" ${c.lead_category_override === k ? "selected" : ""}>Override: ${label(k)}</option>`).join("")}
                </select><button class="btn sm" id="cat-save">Apply</button></div>` : ""}
              <ul class="breakdown">${b.items.map((i) => `<li><span>${esc(i.label)}</span><span class="${i.points >= 0 ? "pos" : "neg"}">${i.points > 0 ? "+" : ""}${i.points}</span></li>`).join("")}
                <li><strong>Total${b.bounded ? ` (raw ${b.raw_total}, bounded 0–100)` : ""}</strong><strong>${b.score}</strong></li></ul>
            </div></div>
          <div class="next-action mt"><div class="lbl">Recommended next action</div><div style="margin-top:4px;font-weight:550">${esc(data.recommended_next_action)}</div></div>
          <div class="card mt"><div class="card-head"><h3>Details</h3></div><div class="card-body"><dl class="kv">
            <dt>Email</dt><dd>${esc(c.email || "—")}</dd><dt>Phone</dt><dd>${esc(c.phone || "—")}</dd>
            <dt>Lifecycle</dt><dd>${stageLabel(c.lifecycle_stage)}</dd><dt>Status</dt><dd>${label(c.lead_status)}</dd>
            <dt>Lead source</dt><dd>${esc(c.lead_source || "—")}</dd>
            <dt>Data sources</dt><dd>${c.sources.length ? c.sources.map((s) => `<span class="badge ${s.source_type === "seed" ? "amber" : s.source_type === "csv" ? "blue" : "gray"} plain">${esc(s.source_name)}</span>`).join(" ") : "—"}</dd>
            <dt>Created</dt><dd>${fmtDate(c.created_at, true)}</dd><dt>Updated</dt><dd>${fmtDate(c.updated_at, true)}</dd>
          </dl></div></div>
          ${co ? `<div class="card mt"><div class="card-head"><h3>Company</h3><a class="btn sm" href="/companies/${co.company_id}">View profile</a></div><div class="card-body">
            <div class="cell-main mb"><span class="avatar company">${esc(initials(co.company_name))}</span><div><div class="t">${esc(co.company_name)}</div><div class="s">${esc(co.industry || "")}</div></div></div>
            <dl class="kv"><dt>Website</dt><dd>${co.website ? `<a href="${esc(co.website)}" target="_blank" rel="noopener noreferrer">${esc(co.website.replace("https://", ""))}</a>` : "—"}</dd>
            <dt>Location</dt><dd>${esc([co.city, co.country].filter(Boolean).join(", ") || "—")}</dd>
            <dt>Employees</dt><dd>${co.employee_count?.toLocaleString() ?? "—"}</dd><dt>Revenue</dt><dd>${fmtMoney(co.annual_revenue)}</dd>
            <dt>Contacts</dt><dd>${co.contact_count}</dd></dl></div></div>`
            : `<div class="card mt"><div class="card-body"><p class="muted" style="margin:0 0 10px">Not associated with a company.</p><button class="btn sm" id="assign-co">Assign company</button></div></div>`}
        </div>
      </div>`;
    bind();
  }

  function bind() {
    const reloadAfter = () => load();
    $("#log-act").onclick = () => activityForm(id, { onSaved: reloadAfter });
    $("#log-act-2")?.addEventListener("click", () => activityForm(id, { onSaved: reloadAfter }));
    $("#edit").onclick = () => contactForm(data.contact, { onSaved: reloadAfter });
    $("#assign-co")?.addEventListener("click", () => contactForm(data.contact, { onSaved: reloadAfter }));
    $("#delete").onclick = async () => {
      if (!(await confirmDialog(`Delete <strong>${esc(data.contact.full_name)}</strong> and all ${data.activity_count} activities? This cannot be undone.`, { confirmLabel: "Delete contact" }))) return;
      try { await api("DELETE", `/api/contacts/${id}`); toast("Contact deleted."); location.href = "/contacts"; }
      catch (e) { toast(e.message, "error"); }
    };
    $("#cat-save")?.addEventListener("click", () => {
      const value = $("#cat-select").value || null;
      if ((value || null) === (data.contact.lead_category_override || null)) return toast("No change to apply.", "info");
      modal({
        title: value ? `Override category to ${label(value)}` : "Return to automatic category", submitLabel: "Apply change",
        body: `<p style="margin-top:0">The automatic category (<strong>${label(data.contact.lead_category_auto)}</strong>) is preserved and this change is recorded in the audit log.</p>
          ${App.field("reason", "Reason (optional)", { full: true, placeholder: "e.g. Met at conference, budget confirmed" })}`,
        onSubmit: async (form) => {
          await api("PUT", `/api/leads/${id}/category`, { category: value, reason: App.formData(form).reason });
          toast("Lead category updated."); load();
        },
      });
    });
    $$("[data-edit-act]", root).forEach((btn) => btn.onclick = () => {
      const a = data.activities.find((x) => x.activity_id === +btn.dataset.editAct);
      activityForm(id, { activity: a, onSaved: reloadAfter });
    });
    $$("[data-del-act]", root).forEach((btn) => btn.onclick = async () => {
      if (!(await confirmDialog("Delete this activity? The lead score will be recalculated.", { confirmLabel: "Delete activity" }))) return;
      try { const r = await api("DELETE", `/api/activities/${btn.dataset.delAct}`); toast(`Activity deleted. Score is now ${r.contact.lead_score}.`); load(); }
      catch (e) { toast(e.message, "error"); }
    });
  }

  async function load() {
    try { data = await get(`/api/contacts/${id}`); render(); }
    catch (e) { root.innerHTML = `<div class="card">${errorHTML(e.message)}</div>`; }
  }
  load();
})();
