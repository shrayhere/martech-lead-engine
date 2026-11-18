(function () {
  const { get, api, qs, esc, $, $$, fmtDate, fmtNum, label, toast, confirmDialog, modal, renderPagination, loadingHTML,
    errorHTML, emptyHTML, download } = App;
  const CSRF = document.querySelector('meta[name="csrf-token"]').content;
  let job = null, columns = [], stats = [], mapping = {}, fields = [], mode = "upsert", lastPreview = null;
  const MODE_LABELS = { insert_only: "Insert only", update_existing: "Update existing", upsert: "Upsert" };
  const STATUS_BADGE = { completed: "green", rolled_back: "red", failed: "red", processing: "blue", previewed: "amber", uploaded: "gray" };
  const ACTION_BADGE = { inserted: "green", updated: "blue", unchanged: "gray", skipped: "gray", duplicate: "amber", review: "amber", failed: "red" };

  // ---------------------------------------------------------------- stepper
  function goto(step) {
    $$("[data-panel]").forEach((p) => p.classList.toggle("hidden", +p.dataset.panel !== step));
    $$("#stepper .step").forEach((s) => {
      const n = +s.dataset.step;
      s.classList.toggle("active", n === step); s.classList.toggle("done", n < step);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  $$("[data-goto]").forEach((b) => b.addEventListener("click", () => goto(+b.dataset.goto)));
  $("#restart").onclick = () => { job = null; lastPreview = null; $("#file-input").value = ""; $("#preview-result").innerHTML = ""; $("#execute").disabled = true; history.replaceState(null, "", "/imports"); goto(1); };

  // ---------------------------------------------------------------- upload
  const dz = $("#dropzone"), input = $("#file-input");
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
  dz.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) uploadFile(f); });
  input.addEventListener("change", () => { if (input.files[0]) uploadFile(input.files[0]); });

  function uploadFile(file) {
    if (!/\.csv$/i.test(file.name)) return toast("Only .csv files are accepted.", "error");
    if (file.size === 0) return toast("The selected file is empty.", "error");
    if (file.size > window.UPLOAD_LIMIT) return toast(`File is too large (${(file.size / 1048576).toFixed(1)} MB). Limit is ${window.UPLOAD_LIMIT / 1048576} MB.`, "error");
    const fd = new FormData(); fd.append("file", file);
    const xhr = new XMLHttpRequest();
    $("#upload-progress").classList.remove("hidden");
    $("#upload-label").textContent = `Uploading ${file.name}…`;
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) $("#upload-bar").style.width = `${Math.round(e.loaded / e.total * 100)}%`; };
    xhr.onload = () => {
      $("#upload-progress").classList.add("hidden"); $("#upload-bar").style.width = "0%"; input.value = "";
      let data = {}; try { data = JSON.parse(xhr.responseText); } catch (_) {}
      if (xhr.status === 401) { location.href = "/login?next=/imports"; return; }
      if (xhr.status !== 201) return toast(data.error || `Upload failed (${xhr.status}).`, "error");
      toast(`Uploaded ${data.job.original_filename}: ${fmtNum(data.job.total_rows)} rows detected.`);
      startMapping(data); loadHistory();
    };
    xhr.onerror = () => { $("#upload-progress").classList.add("hidden"); toast("Network error during upload.", "error"); };
    xhr.open("POST", "/api/imports/upload"); xhr.setRequestHeader("X-CSRFToken", CSRF); xhr.send(fd);
  }

  // ---------------------------------------------------------------- mapping
  async function startMapping(data) {
    job = data.job; columns = data.columns; stats = data.column_stats; mapping = { ...data.suggested_mapping };
    columns.forEach((c) => { if (!(c in mapping)) mapping[c] = ""; });
    if (!fields.length) fields = (await get("/api/imports/fields")).fields;
    $("#file-meta").innerHTML = `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
      <span class="badge blue plain">📄 ${esc(job.original_filename)}</span><span class="badge gray plain">${fmtNum(job.total_rows)} rows</span>
      <span class="badge gray plain">${columns.length} columns</span><span class="badge gray plain">${esc(data.delimiter_label || job.delimiter)} delimited</span>
      <span class="badge gray plain">${esc(job.encoding)} encoding</span><span class="badge gray plain">${(job.file_size / 1024).toFixed(1)} KB</span></div>`;
    $("#upload-warnings").innerHTML = (data.warnings || []).map((w) => `<div class="form-error" style="background:var(--warning-bg);color:var(--warning);border-color:var(--warm-border)">⚠ ${esc(w)}</div>`).join("");
    renderMapping(); renderPreview(data.preview || []);
    lastPreview = null; $("#preview-result").innerHTML = ""; $("#execute").disabled = true;
    goto(2);
  }
  function fieldOptions(selected) {
    const groups = {};
    fields.forEach((f) => (groups[f.group] = groups[f.group] || []).push(f));
    return `<option value="">— Ignore this column —</option>` + Object.entries(groups).map(([g, fs]) =>
      `<optgroup label="${g}">${fs.map((f) => `<option value="${f.field}" ${f.field === selected ? "selected" : ""}>${esc(f.label)}</option>`).join("")}</optgroup>`).join("");
  }
  function renderMapping() {
    const used = Object.values(mapping).filter(Boolean);
    $("#mapping").innerHTML = columns.map((col) => {
      const s = stats.find((x) => x.column === col) || { samples: [], fill_rate: 0 };
      const dup = mapping[col] && used.filter((u) => u === mapping[col]).length > 1;
      return `<div class="map-row"><div><div class="col-name">${esc(col)}</div><div class="samples" title="${esc(s.samples.join(" | "))}">${s.samples.length ? esc(s.samples.join(" · ")) : "<em>empty</em>"}</div></div>
        <div class="arrow-ico muted">→</div>
        <div class="field ${dup ? "has-error" : ""}"><select class="input sm" data-col="${esc(col)}">${fieldOptions(mapping[col])}</select>${dup ? '<span class="err">Mapped twice</span>' : ""}</div>
        <div class="small muted">${s.fill_rate}% filled · ${fmtNum(s.unique)} unique</div></div>`;
    }).join("");
    $$("#mapping select").forEach((sel) => sel.addEventListener("change", () => { mapping[sel.dataset.col] = sel.value; renderMapping(); lastPreview = null; $("#execute").disabled = true; }));
    renderChecklist();
  }
  function renderChecklist() {
    const t = new Set(Object.values(mapping).filter(Boolean));
    const dupes = Object.values(mapping).filter(Boolean).filter((v, i, a) => a.indexOf(v) !== i);
    const checks = [
      [t.has("email") || t.has("phone"), "Identifier mapped (Email or Phone)", true],
      [t.has("full_name") || t.has("first_name") || t.has("email"), "Name mapped (or derived from email)", true],
      [!(t.has("full_name") && (t.has("first_name") || t.has("last_name"))), "Not both Full name and First/Last name", true],
      [!dupes.length, "Each field mapped once", true],
      [t.has("email"), "Email mapped (strongest duplicate matching)", false],
      [t.has("company_name"), "Company mapped (contacts linked to companies)", false],
      [t.has("activity_type") || t.has("activity_date"), "Activity mapped (drives lead scoring)", false],
    ];
    $("#map-check").innerHTML = checks.map(([ok, text, req]) => `<div class="quality-item"><span>${ok ? "✅" : req ? "❌" : "⚪"} ${esc(text)}</span>${req ? '<span class="badge gray plain">required</span>' : '<span class="small muted">recommended</span>'}</div>`).join("")
      + `<p class="small muted" style="margin:12px 0 0">${t.size} of ${columns.length} columns mapped.</p>`;
    $("#to-step-3").disabled = !checks.filter((c) => c[2]).every((c) => c[0]);
  }
  function renderPreview(rows) {
    $("#preview-table").innerHTML = rows.length ? `<table class="table"><thead><tr>${columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${columns.map((c) => `<td class="nowrap">${esc(r[c] ?? "") || '<span class="muted">∅</span>'}</td>`).join("")}</tr>`).join("")}</tbody></table>`
      : emptyHTML("No preview available", "The file has no readable rows.");
  }
  $("#auto-map").onclick = async () => {
    const res = await get(`/api/imports/${job.import_id}`).catch((e) => toast(e.message, "error"));
    if (!res || !res.auto_mapping) return;
    mapping = {}; columns.forEach((c) => (mapping[c] = res.auto_mapping[c] || ""));
    lastPreview = null; $("#execute").disabled = true;
    renderMapping(); toast("Columns auto-detected.", "info");
  };
  $("#to-step-3").onclick = () => goto(3);

  // ---------------------------------------------------------------- preview / execute
  $("#modes").addEventListener("click", (e) => {
    const c = e.target.closest("[data-mode]"); if (!c) return;
    mode = c.dataset.mode; $$("#modes .mode-card").forEach((m) => m.classList.toggle("active", m === c));
    lastPreview = null; $("#execute").disabled = true; $("#preview-result").innerHTML = `<p class="muted small">Mode changed: run the preview again.</p>`;
  });

  const tile = (v, l, color) => `<div class="summary-tile"><div class="v" style="${color ? `color:${color}` : ""}">${fmtNum(v)}</div><div class="l">${l}</div></div>`;
  function summaryTiles(s) {
    return `<div class="summary-grid">${tile(s.total_processed, "Records processed")}${tile(s.inserted, "New records inserted", "var(--success)")}
      ${tile(s.updated, "Existing records updated", "var(--primary)")}${tile(s.duplicates, `Duplicates detected (${s.needs_review} need review)`, "var(--warning)")}
      ${tile(s.skipped, "Records skipped")}${tile(s.invalid, "Invalid / failed rows", "var(--danger)")}
      ${tile(s.companies_created, `Companies created (${s.companies_updated} updated)`)}${tile(s.activities_added, "Activities added")}</div>`;
  }
  function rowsTable(rows, truncated, total) {
    const counts = rows.reduce((a, r) => ((a[r.action] = (a[r.action] || 0) + 1), a), {});
    return `<div class="card mt"><div class="card-head"><div><h3>Row-by-row outcome</h3><p>${truncated ? `First ${rows.length} of ${fmtNum(total)} rows` : `${rows.length} rows`}</p></div>
      <div class="segmented" id="row-filter"><button class="active" data-f="">All</button>${Object.keys(counts).map((k) => `<button data-f="${k}">${label(k)} (${counts[k]})</button>`).join("")}</div></div>
      <div class="table-wrap" style="max-height:420px;overflow:auto"><table class="table"><thead><tr><th>Row</th><th>Outcome</th><th>Name</th><th>Email / phone</th><th>Company</th><th>Details</th></tr></thead>
      <tbody id="rows-body">${rows.map((r) => `<tr data-a="${r.action}"><td>${r.row}</td><td><span class="badge ${ACTION_BADGE[r.action] || "gray"} plain row-action">${label(r.action)}</span></td>
        <td>${r.contact_id && r.action !== "failed" && !lastPreview?.dry_run ? `<a href="/contacts/${r.contact_id}">${esc(r.name || "—")}</a>` : esc(r.name || "—")}</td>
        <td class="small">${esc(r.email || r.phone || "—")}</td><td class="small">${esc(r.company || "—")}</td>
        <td class="small">${r.reason ? esc(r.reason) : ""}${r.changes?.length ? `Changed: ${esc(r.changes.join(", "))}` : ""}${r.lead_category ? ` <span class="badge ${r.lead_category} plain">${label(r.lead_category)} · ${r.lead_score}</span>` : ""}
          ${r.warnings?.length ? `<div class="muted">⚠ ${esc(r.warnings.join(" · "))}</div>` : ""}</td></tr>`).join("")}</tbody></table></div></div>`;
  }
  function bindRowFilter(root) {
    $("#row-filter", root)?.addEventListener("click", (e) => {
      const b = e.target.closest("[data-f]"); if (!b) return;
      $$("#row-filter button", root).forEach((x) => x.classList.toggle("active", x === b));
      $$("#rows-body tr", root).forEach((tr) => tr.classList.toggle("hidden", !!b.dataset.f && tr.dataset.a !== b.dataset.f));
    });
  }

  $("#run-preview").onclick = async () => {
    const out = $("#preview-result"), btn = $("#run-preview");
    out.innerHTML = `<div class="small muted mb">Running dry run (${MODE_LABELS[mode]})…</div><div class="progress indeterminate"><span></span></div>`;
    btn.disabled = true;
    try {
      lastPreview = await api("POST", "/api/imports/preview", { import_id: job.import_id, mapping, mode });
      const s = lastPreview.summary;
      out.innerHTML = `<div class="card" style="border-color:var(--primary-100)"><div class="card-head"><div><h3>Dry-run preview: ${MODE_LABELS[mode]}</h3><p>Nothing has been saved yet · processed in ${s.duration_ms} ms · ${s.warnings} cleaning warning(s)</p></div><span class="badge blue">Preview</span></div>
        <div class="card-body">${summaryTiles(s)}</div></div>${rowsTable(lastPreview.rows, lastPreview.rows_truncated, s.total_processed)}`;
      bindRowFilter(out);
      $("#execute").disabled = s.inserted + s.updated + s.needs_review === 0 && s.duplicates === 0;
      if ($("#execute").disabled) out.insertAdjacentHTML("beforeend", `<p class="small muted mt">This import would not change anything in ${MODE_LABELS[mode]} mode.</p>`);
    } catch (e) {
      out.innerHTML = `<div class="form-error">${esc(e.message)}${e.details ? `<ul style="margin:6px 0 0">${Object.values(e.details).map((d) => `<li>${esc(d)}</li>`).join("")}</ul>` : ""}</div>`;
    } finally { btn.disabled = false; }
  };

  $("#execute").onclick = async () => {
    if (!lastPreview) return;
    const s = lastPreview.summary;
    const ok = await confirmDialog(`Import <strong>${esc(job.original_filename)}</strong> in <strong>${MODE_LABELS[mode]}</strong> mode?<br><br>
      ${s.inserted} new · ${s.updated} updated · ${s.needs_review} sent to duplicate review · ${s.invalid} invalid rows reported.<br>
      <span class="small muted">The whole import is applied in one transaction and rolled back if anything fails.</span>`, { title: "Confirm import", confirmLabel: "Import now", danger: false });
    if (!ok) return;
    goto(4);
    const box = $("#final-report");
    box.innerHTML = `<div style="max-width:520px;margin:30px auto;text-align:center"><h3>Synchronizing ${esc(job.original_filename)}…</h3>
      <p class="muted">Cleaning, matching and writing ${fmtNum(job.total_rows)} rows in a single transaction.</p><div class="progress indeterminate"><span></span></div></div>`;
    try {
      const res = await api("POST", "/api/imports/execute", { import_id: job.import_id, mapping, mode });
      lastPreview = null;
      renderFinal(res); loadHistory(); toast("Import completed successfully.");
    } catch (e) {
      box.innerHTML = `<div class="form-error"><strong>Import failed and was rolled back. No changes were saved.</strong><br>${esc(e.message)}</div>
        <div class="page-actions"><button class="btn" id="back-3">Back to preview</button></div>`;
      $("#back-3").onclick = () => goto(3);
      loadHistory();
    }
  };

  function reportLinks(j, pendingDup) {
    return `<div class="page-actions mt">
      ${j.has_success_report ? `<a class="btn" href="/api/imports/${j.import_id}/report?download=success">⬇ Successful import report</a>` : ""}
      ${j.has_error_report ? `<a class="btn" href="/api/imports/${j.import_id}/errors">⬇ Failed records CSV</a>` : ""}
      ${j.has_duplicate_report ? `<a class="btn" href="/api/imports/${j.import_id}/report?download=duplicates">⬇ Duplicate records CSV</a>` : ""}
      ${pendingDup ? `<a class="btn primary" href="/data">Review ${pendingDup} duplicate(s) →</a>` : ""}
      <a class="btn" href="/contacts?sort=updated">View contacts</a></div>`;
  }
  function renderFinal(res) {
    const s = res.summary, j = res.job;
    $("#final-report").innerHTML = `<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center" class="mb">
      <div><h2>✅ Synchronization complete</h2><p class="muted" style="margin:4px 0 0">${esc(j.original_filename)} · ${MODE_LABELS[res.mode]} · processed in ${(s.duration_ms / 1000).toFixed(2)} s</p></div>
      <span class="badge green">Completed</span></div>${summaryTiles(s)}${reportLinks(j, s.needs_review)}${rowsTable(res.rows, res.rows_truncated, s.total_processed)}`;
    bindRowFilter($("#final-report"));
  }

  // ---------------------------------------------------------------- history
  let hPage = 1;
  async function loadHistory() {
    const body = $("#history"); body.innerHTML = `<tr><td colspan="10">${loadingHTML}</td></tr>`;
    try {
      const data = await get("/api/imports/history" + qs({ page: hPage, per_page: 10 }));
      body.innerHTML = data.items.length ? data.items.map((j) => `<tr>
        <td><strong>${esc(j.original_filename)}</strong><div class="small muted">#${j.import_id} · ${(j.file_size / 1024).toFixed(1)} KB</div></td>
        <td class="nowrap">${fmtDate(j.upload_timestamp, true)}</td><td>${j.sync_mode ? MODE_LABELS[j.sync_mode] : "—"}</td>
        <td><span class="badge ${STATUS_BADGE[j.import_status] || "gray"}" title="${esc(j.error_message || "")}">${label(j.import_status)}</span></td>
        <td>${fmtNum(j.total_rows)}</td><td>${j.import_status === "completed" ? fmtNum(j.inserted_rows) : "—"}</td>
        <td>${j.import_status === "completed" ? fmtNum(j.updated_rows) : "—"}</td><td>${j.import_status === "completed" ? fmtNum(j.duplicate_rows) : "—"}</td>
        <td>${j.import_status === "completed" ? fmtNum(j.failed_rows) : "—"}</td>
        <td class="actions">${["uploaded", "previewed"].includes(j.import_status) ? `<button class="btn sm" data-resume="${j.import_id}">Continue</button>`
          : `<button class="btn sm" data-report="${j.import_id}">Report</button>`}</td></tr>`).join("")
        : `<tr><td colspan="10">${emptyHTML("No imports yet", "Upload your first CSV above.")}</td></tr>`;
      renderPagination($("#history-pages"), data, (p) => { hPage = p; loadHistory(); });
    } catch (e) { body.innerHTML = `<tr><td colspan="10">${errorHTML(e.message)}</td></tr>`; }
  }
  $("#history").addEventListener("click", async (e) => {
    const r = e.target.closest("[data-resume]"), rep = e.target.closest("[data-report]");
    if (r) {
      try {
        const d = await get(`/api/imports/${r.dataset.resume}`);
        if (d.file_error) return toast(d.file_error, "error");
        startMapping({ job: d.job, columns: d.columns, column_stats: d.column_stats, suggested_mapping: d.suggested_mapping, preview: d.preview });
      } catch (err) { toast(err.message, "error"); }
    }
    if (rep) showReport(+rep.dataset.report);
  });
  async function showReport(id) {
    try {
      const d = await get(`/api/imports/${id}/report`), j = d.job;
      const s = { total_processed: j.total_rows, inserted: j.inserted_rows, updated: j.updated_rows, duplicates: j.duplicate_rows,
        needs_review: d.pending_duplicates, skipped: j.skipped_rows, invalid: j.failed_rows, companies_created: "—", companies_updated: "—", activities_added: "—" };
      modal({ title: `Import #${j.import_id}: ${j.original_filename}`, wide: true, hideSubmit: true, cancelLabel: "Close",
        body: `<p class="muted" style="margin-top:0">${label(j.import_status)} · ${j.sync_mode ? MODE_LABELS[j.sync_mode] : "not executed"} · uploaded ${fmtDate(j.upload_timestamp, true)}
          ${j.duration_ms != null ? ` · processing time ${(j.duration_ms / 1000).toFixed(2)} s` : ""}</p>
          ${j.error_message ? `<div class="form-error">${esc(j.error_message)}</div>` : ""}
          ${j.import_status === "completed" ? `<div class="summary-grid">${tile(s.total_processed, "Records processed")}${tile(s.inserted, "Inserted", "var(--success)")}${tile(s.updated, "Updated", "var(--primary)")}
            ${tile(s.duplicates, "Duplicates detected", "var(--warning)")}${tile(s.skipped, "Skipped")}${tile(s.invalid, "Invalid / failed", "var(--danger)")}${tile(d.pending_duplicates, "Awaiting duplicate review", "var(--warning)")}</div>` : ""}
          ${d.sync_logs.length ? `<h3 class="mt">Synchronization log</h3><table class="table mt"><thead><tr><th>Sync</th><th>Type</th><th>Status</th><th>Inserted</th><th>Updated</th><th>Skipped</th><th>Failed</th><th>Source</th></tr></thead><tbody>
            ${d.sync_logs.map((l) => `<tr><td>#${l.sync_id}</td><td>${MODE_LABELS[l.sync_type] || l.sync_type}</td><td>${label(l.sync_status)}</td><td>${l.records_inserted}</td><td>${l.records_updated}</td><td>${l.records_skipped}</td><td>${l.records_failed}</td><td>${esc(l.source?.source_name || "—")}</td></tr>`).join("")}</tbody></table>` : ""}
          ${reportLinks(j, d.pending_duplicates)}` });
    } catch (e) { toast(e.message, "error"); }
  }

  loadHistory();
  const reportParam = new URLSearchParams(location.search).get("report");
  if (reportParam) showReport(+reportParam);
})();
