/* MarTech CRM — shared front-end library (no framework; Fetch API + DOM). */
(function () {
  "use strict";
  const CSRF = document.querySelector('meta[name="csrf-token"]')?.content;

  // ------------------------------------------------------------------ API
  class ApiError extends Error {
    constructor(message, status, details) { super(message); this.status = status; this.details = details || {}; }
  }

  async function api(method, url, body, opts = {}) {
    const init = { method, credentials: "same-origin", headers: { "X-CSRFToken": CSRF, Accept: "application/json" } };
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    let res;
    try { res = await fetch(url, init); }
    catch (e) { throw new ApiError("Network error: the server could not be reached.", 0); }
    if (res.status === 401 && !opts.allow401) {
      location.href = "/login?next=" + encodeURIComponent(location.pathname + location.search);
      throw new ApiError("Session expired", 401);
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(data.error || `Request failed (${res.status})`, res.status, data.details);
    return data;
  }
  const get = (url) => api("GET", url);
  const qs = (obj) => {
    const p = new URLSearchParams();
    Object.entries(obj).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, v); });
    const s = p.toString(); return s ? "?" + s : "";
  };

  // ------------------------------------------------------------------ helpers
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const parseDate = (iso) => (iso ? new Date(iso.endsWith("Z") ? iso : iso + "Z") : null);
  function fmtDate(iso, withTime = false) {
    const d = parseDate(iso); if (!d || isNaN(d)) return "—";
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric",
      ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}) });
  }
  function fmtRelative(iso) {
    const d = parseDate(iso); if (!d) return "Never";
    const s = (Date.now() - d.getTime()) / 1000;
    if (s < 60) return "just now";
    const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
    for (const [u, n] of units) if (Math.abs(s) >= n) {
      const v = Math.round(s / n); return v > 0 ? `${v} ${u}${v > 1 ? "s" : ""} ago` : `in ${-v} ${u}${v < -1 ? "s" : ""}`;
    }
    return "just now";
  }
  const fmtNum = (n) => (n ?? 0).toLocaleString();
  const fmtMoney = (n) => (n == null ? "—" : new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n));
  const initials = (name) => (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");
  const label = (s) => (s ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "—");
  const STAGE_LABELS = { mql: "MQL", sql: "SQL" };
  const stageLabel = (s) => STAGE_LABELS[s] || label(s);
  const CAT_COLORS = { hot: "#dc2626", warm: "#d97706", cold: "#64748b" };

  function categoryBadge(c) {
    const cat = c.lead_category;
    if (!cat) return `<span class="badge excluded" title="No valid email or phone — excluded from qualification">Excluded</span>`;
    const ovr = c.lead_category_override ? ` <span class="ovr" title="Manual override (auto: ${esc(c.lead_category_auto)})">✎</span>` : "";
    return `<span class="badge ${cat}">${label(cat)}${ovr}</span>`;
  }
  function scoreBar(score, cat) {
    const color = CAT_COLORS[cat] || "#94a3b8";
    return `<span class="score"><span class="bar"><span style="width:${Math.max(2, score)}%;background:${color}"></span></span><b>${score}</b></span>`;
  }
  function debounce(fn, ms = 250) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
  function download(url) { window.location.href = url; }
  const loadingHTML = `<div class="loading"><div class="spinner"></div></div>`;
  function emptyHTML(title, text, action = "") {
    return `<div class="empty"><div class="ill"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>
      <h3>${esc(title)}</h3><p>${esc(text)}</p>${action}</div>`;
  }
  const errorHTML = (msg) => `<div class="error-state">⚠ ${esc(msg)}</div>`;

  // ------------------------------------------------------------------ toast
  function toast(message, type = "success") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${type === "error" ? "⚠" : type === "info" ? "ℹ" : "✓"}</span><span>${esc(message)}</span>`;
    $("#toasts").appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(() => el.remove(), 300); }, type === "error" ? 6000 : 3500);
  }

  // ------------------------------------------------------------------ modal
  function modal({ title, body, submitLabel = "Save", cancelLabel = "Cancel", wide = false, danger = false, onSubmit, hideSubmit = false, onOpen }) {
    const back = document.createElement("div");
    back.className = "modal-backdrop";
    back.innerHTML = `<div class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true">
      <div class="modal-head"><h2>${esc(title)}</h2><button class="icon-btn" data-close aria-label="Close">✕</button></div>
      <form class="modal-form" novalidate><div class="modal-body"><div class="form-error hidden"></div>${body}</div>
      <div class="modal-foot"><button type="button" class="btn" data-close>${esc(cancelLabel)}</button>
      ${hideSubmit ? "" : `<button type="submit" class="btn ${danger ? "danger solid" : "primary"}">${esc(submitLabel)}</button>`}</div></form></div>`;
    document.body.appendChild(back);
    const form = $("form", back);
    const close = () => { back.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    back.addEventListener("mousedown", (e) => { if (e.target === back) close(); });
    $$("[data-close]", back).forEach((b) => b.addEventListener("click", close));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!onSubmit) return close();
      const btn = $('button[type="submit"]', form);
      clearErrors(form);
      btn.disabled = true; const txt = btn.textContent; btn.innerHTML = `<span class="spinner"></span> ${esc(txt)}`;
      try { const keep = await onSubmit(form, close); if (keep !== false) close(); }
      catch (err) { showErrors(form, err); }
      finally { btn.disabled = false; btn.textContent = txt; }
    });
    setTimeout(() => $("input:not([type=hidden]):not([type=checkbox]), select, textarea", form)?.focus(), 30);
    if (onOpen) onOpen(form, close);
    return { el: back, form, close };
  }

  function confirmDialog(message, { title = "Are you sure?", confirmLabel = "Confirm", danger = true } = {}) {
    return new Promise((resolve) => {
      let done = false;
      const m = modal({ title, body: `<p style="margin:0">${message}</p>`, submitLabel: confirmLabel, danger,
        onSubmit: async () => { done = true; resolve(true); } });
      const obs = new MutationObserver(() => { if (!document.body.contains(m.el)) { obs.disconnect(); if (!done) resolve(false); } });
      obs.observe(document.body, { childList: true });
    });
  }

  function clearErrors(form) {
    $(".form-error", form)?.classList.add("hidden");
    $$(".field", form).forEach((f) => { f.classList.remove("has-error"); $(".err", f)?.remove(); });
  }
  function showErrors(form, err) {
    const box = $(".form-error", form);
    if (box) { box.textContent = err.message || "Something went wrong."; box.classList.remove("hidden"); }
    Object.entries(err.details || {}).forEach(([k, msg]) => {
      const input = form.querySelector(`[name="${k}"]`); if (!input || typeof msg !== "string") return;
      const field = input.closest(".field"); if (!field) return;
      field.classList.add("has-error");
      const s = document.createElement("span"); s.className = "err"; s.textContent = msg; field.appendChild(s);
    });
    if (!box) toast(err.message, "error");
  }
  function formData(form) {
    const out = {};
    $$("[name]", form).forEach((el) => {
      if (el.type === "checkbox") out[el.name] = el.checked;
      else if (el.type === "radio") { if (el.checked) out[el.name] = el.value; }
      else out[el.name] = el.value.trim() === "" ? null : el.value.trim();
    });
    return out;
  }
  const field = (name, lbl, { type = "text", value = "", required = false, full = false, placeholder = "", hint = "", attrs = "" } = {}) =>
    `<div class="field ${full ? "full" : ""}"><label for="f-${name}">${esc(lbl)}${required ? ' <span class="req">*</span>' : ""}</label>
     ${type === "textarea" ? `<textarea class="input" id="f-${name}" name="${name}" placeholder="${esc(placeholder)}" ${attrs}>${esc(value)}</textarea>`
      : `<input class="input" id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" placeholder="${esc(placeholder)}" ${required ? "required" : ""} ${attrs}>`}
     ${hint ? `<span class="hint">${esc(hint)}</span>` : ""}</div>`;
  const selectField = (name, lbl, options, value, { full = false, required = false } = {}) =>
    `<div class="field ${full ? "full" : ""}"><label for="f-${name}">${esc(lbl)}${required ? ' <span class="req">*</span>' : ""}</label>
     <select class="input" id="f-${name}" name="${name}">${options.map(([v, l]) => `<option value="${esc(v)}" ${String(v) === String(value ?? "") ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></div>`;

  // ------------------------------------------------------------------ searchable company picker
  function companyPicker(container, initial) {
    // initial: {company_id, company_name} | null
    let state = { mode: initial ? "existing" : "none", company: initial || null };
    container.innerHTML = `<input type="hidden" name="company_id"><div class="combo"></div>`;
    const hidden = $('input[name="company_id"]', container);
    const combo = $(".combo", container);
    function render() {
      hidden.value = state.mode === "existing" && state.company ? state.company.company_id : "";
      if (state.mode === "existing" && state.company) {
        combo.innerHTML = `<div class="selected-chip"><span>🏢 <strong>${esc(state.company.company_name)}</strong></span>
          <button type="button" class="link-btn small" data-clear>Change</button></div>`;
        $("[data-clear]", combo).onclick = () => { state = { mode: "none", company: null }; render(); $("input", combo)?.focus(); };
      } else if (state.mode === "new") {
        combo.innerHTML = `<div class="selected-chip"><span>➕ New company: <strong>${esc(state.name)}</strong></span>
          <button type="button" class="link-btn small" data-clear>Change</button></div>
          <input type="hidden" name="new_company_name" value="${esc(state.name)}">`;
        $("[data-clear]", combo).onclick = () => { state = { mode: "none", company: null }; render(); };
      } else {
        combo.innerHTML = `<input class="input" placeholder="Search companies or type a new name…" autocomplete="off" aria-label="Company">
          <div class="dropdown hidden"></div>`;
        const input = $("input", combo), dd = $(".dropdown", combo);
        const search = debounce(async () => {
          const term = input.value.trim();
          try {
            const { items } = await get("/api/companies/options" + qs({ q: term }));
            const exact = items.some((c) => c.company_name.toLowerCase() === term.toLowerCase());
            dd.innerHTML = items.map((c) => `<button type="button" class="item" data-id="${c.company_id}" data-name="${esc(c.company_name)}">🏢 ${esc(c.company_name)} <span class="muted small">${esc(c.industry || "")}</span></button>`).join("")
              + (term && !exact ? `<div class="sep"></div><button type="button" class="item" data-new="${esc(term)}">➕ Create “${esc(term)}”</button>` : "")
              + (!items.length && !term ? `<div class="muted small" style="padding:8px 10px">No companies yet — type a name to create one.</div>` : "");
            dd.classList.remove("hidden");
            $$("[data-id]", dd).forEach((b) => b.onclick = () => { state = { mode: "existing", company: { company_id: +b.dataset.id, company_name: b.dataset.name } }; render(); });
            $$("[data-new]", dd).forEach((b) => b.onclick = () => { state = { mode: "new", name: b.dataset.new }; render(); });
          } catch (e) { dd.innerHTML = errorHTML(e.message); dd.classList.remove("hidden"); }
        }, 200);
        input.addEventListener("input", search);
        input.addEventListener("focus", search);
        input.addEventListener("blur", () => setTimeout(() => dd.classList.add("hidden"), 180));
      }
    }
    render();
    return {
      payload() {
        if (state.mode === "existing") return { company_id: state.company.company_id };
        if (state.mode === "new") return { new_company: { company_name: state.name } };
        return { company_id: null };
      },
    };
  }

  // ------------------------------------------------------------------ shared forms
  const LIFECYCLE = (window.MARTECH?.lifecycle || []).map((s) => [s, stageLabel(s)]);
  const STATUSES = [["new", "New"], ["open", "Open"], ["in_progress", "In progress"], ["qualified", "Qualified"], ["unqualified", "Unqualified"]];

  function contactForm(contact, { onSaved, presetCompany } = {}) {
    const c = contact || {};
    let picker;
    modal({
      title: contact ? `Edit ${c.full_name}` : "New contact", wide: true, submitLabel: contact ? "Save changes" : "Create contact",
      body: `<div class="form-grid">
        ${field("first_name", "First name", { value: c.first_name, required: true })}
        ${field("last_name", "Last name", { value: c.last_name })}
        ${field("email", "Email", { type: "email", value: c.email, placeholder: "name@company.com" })}
        ${field("phone", "Phone", { value: c.phone, placeholder: "+1 415 555 0100" })}
        ${field("job_title", "Job title", { value: c.job_title })}
        <div class="field"><label>Company</label><div id="company-picker"></div></div>
        ${selectField("lifecycle_stage", "Lifecycle stage", LIFECYCLE, c.lifecycle_stage || "lead")}
        ${contact && c.lead_status !== "excluded" ? selectField("lead_status", "Lead status", STATUSES, c.lead_status) : ""}
        ${field("lead_source", "Lead source", { value: c.lead_source, placeholder: "Website, Referral, Webinar…", attrs: 'list="lead-source-list"' })}
        <datalist id="lead-source-list"></datalist>
        <p class="full small muted" style="margin:0">A valid email or phone is required for the contact to be qualified as a lead. Lead scores are calculated from activities.</p>
      </div>`,
      onOpen: (form) => {
        picker = companyPicker($("#company-picker", form), c.company || presetCompany || null);
        get("/api/leads/sources").then(({ items }) => { $("#lead-source-list", form).innerHTML = items.map((s) => `<option value="${esc(s)}">`).join(""); }).catch(() => {});
      },
      onSubmit: async (form) => {
        const data = formData(form);
        delete data.new_company_name;
        Object.assign(data, picker.payload());
        const res = contact ? await api("PUT", `/api/contacts/${c.contact_id}`, data) : await api("POST", "/api/contacts", data);
        toast(contact ? "Contact updated." : "Contact created.");
        onSaved ? onSaved(res.contact) : (location.href = `/contacts/${res.contact.contact_id}`);
      },
    });
  }

  function companyForm(company, { onSaved } = {}) {
    const c = company || {};
    modal({
      title: company ? `Edit ${c.company_name}` : "New company", wide: true, submitLabel: company ? "Save changes" : "Create company",
      body: `<div class="form-grid">
        ${field("company_name", "Company name", { value: c.company_name, required: true, full: true })}
        ${field("industry", "Industry", { value: c.industry })}
        ${field("website", "Website", { value: c.website, placeholder: "example.com" })}
        ${field("company_email", "Company email", { type: "email", value: c.company_email })}
        ${field("phone", "Phone", { value: c.phone })}
        ${field("address", "Address", { value: c.address, full: true })}
        ${field("city", "City", { value: c.city })}
        ${field("country", "Country", { value: c.country })}
        ${field("employee_count", "Employees", { type: "number", value: c.employee_count, attrs: 'min="0"' })}
        ${field("annual_revenue", "Annual revenue", { value: c.annual_revenue, placeholder: "e.g. 5000000 or 5M" })}
        ${field("description", "Description", { type: "textarea", value: c.description, full: true })}
      </div>`,
      onSubmit: async (form) => {
        const data = formData(form);
        const res = company ? await api("PUT", `/api/companies/${c.company_id}`, data) : await api("POST", "/api/companies", data);
        toast(company ? "Company updated." : "Company created.");
        onSaved ? onSaved(res.company) : (location.href = `/companies/${res.company.company_id}`);
      },
    });
  }

  let rulesCache = null;
  async function activityTypes() {
    if (!rulesCache) rulesCache = (await get("/api/settings/scoring-rules")).rules;
    return rulesCache;
  }
  function nowLocal() { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); }
  function toLocalInput(iso) { const d = parseDate(iso); if (!d) return nowLocal(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); }
  function localToUTC(v) { return v ? new Date(v).toISOString().slice(0, 19) : null; }

  async function activityForm(contactId, { activity, onSaved } = {}) {
    let rules;
    try { rules = await activityTypes(); } catch (e) { return toast(e.message, "error"); }
    const opts = rules.map((r) => [r.activity_type, `${r.label} (${r.points > 0 ? "+" : ""}${r.points})`]);
    let picker = null;
    modal({
      title: activity ? "Edit activity" : "Log activity", submitLabel: activity ? "Save" : "Log activity",
      body: `<div class="form-grid">
        ${contactId ? "" : `<div class="field full"><label>Contact <span class="req">*</span></label><div class="combo" id="contact-picker">
           <input class="input" placeholder="Search contacts by name or email…" autocomplete="off"><input type="hidden" name="contact_id"><div class="dropdown hidden"></div></div></div>`}
        ${selectField("activity_type", "Activity type", opts, activity?.activity_type || "website_visit", { full: true, required: true })}
        ${field("activity_date", "Date & time", { type: "datetime-local", value: toLocalInput(activity?.activity_date), full: true })}
        ${field("activity_description", "Notes", { type: "textarea", value: activity?.activity_description, full: true })}
      </div>`,
      onOpen: (form) => {
        if (contactId) return;
        const box = $("#contact-picker", form), input = $("input.input", box), hidden = $('input[type=hidden]', box), dd = $(".dropdown", box);
        input.addEventListener("input", debounce(async () => {
          hidden.value = "";
          const term = input.value.trim(); if (term.length < 2) return dd.classList.add("hidden");
          const { items } = await get("/api/contacts" + qs({ q: term, per_page: 8, sort: "name" }));
          dd.innerHTML = items.length ? items.map((c) => `<button type="button" class="item" data-id="${c.contact_id}" data-name="${esc(c.full_name)}">${esc(c.full_name)} <span class="muted small">${esc(c.email || c.phone || "")}</span></button>`).join("")
            : `<div class="muted small" style="padding:8px 10px">No matching contacts.</div>`;
          dd.classList.remove("hidden");
          $$("[data-id]", dd).forEach((b) => b.onclick = () => { hidden.value = b.dataset.id; input.value = b.dataset.name; dd.classList.add("hidden"); });
        }, 200));
      },
      onSubmit: async (form) => {
        const data = formData(form);
        const cid = contactId || data.contact_id;
        if (!cid) throw new ApiError("Choose a contact from the list.", 422);
        delete data.contact_id;
        data.activity_date = localToUTC(data.activity_date);
        const res = activity ? await api("PUT", `/api/activities/${activity.activity_id}`, data)
          : await api("POST", `/api/contacts/${cid}/activities`, data);
        toast(`Activity saved. Lead score is now ${res.contact.lead_score} (${res.contact.lead_category ? label(res.contact.lead_category) : "excluded"}).`);
        onSaved ? onSaved(res) : (location.href = `/contacts/${cid}`);
      },
    });
  }

  // ------------------------------------------------------------------ pagination & sortable tables
  function renderPagination(el, data, onPage) {
    if (!data.total) { el.innerHTML = ""; return; }
    const start = (data.page - 1) * data.per_page + 1, end = Math.min(data.total, data.page * data.per_page);
    const pages = [];
    const add = (p) => pages.push(`<button class="btn sm ${p === data.page ? "primary" : ""}" data-page="${p}">${p}</button>`);
    const window_ = new Set([1, data.pages, data.page - 1, data.page, data.page + 1].filter((p) => p >= 1 && p <= data.pages));
    let last = 0;
    [...window_].sort((a, b) => a - b).forEach((p) => { if (p - last > 1) pages.push(`<span class="muted">…</span>`); add(p); last = p; });
    el.innerHTML = `<span>Showing <strong>${fmtNum(start)}–${fmtNum(end)}</strong> of <strong>${fmtNum(data.total)}</strong></span>
      <div class="pages"><button class="btn sm" data-page="${data.page - 1}" ${data.page <= 1 ? "disabled" : ""}>‹ Prev</button>${pages.join("")}
      <button class="btn sm" data-page="${data.page + 1}" ${data.page >= data.pages ? "disabled" : ""}>Next ›</button></div>`;
    $$("[data-page]", el).forEach((b) => b.addEventListener("click", () => onPage(+b.dataset.page)));
  }
  function bindSort(table, state, onChange) {
    $$("th[data-sort]", table).forEach((th) => {
      th.classList.add("sortable");
      const update = () => {
        th.classList.toggle("sorted", state.sort === th.dataset.sort);
        th.querySelector(".arrow")?.remove();
        th.insertAdjacentHTML("beforeend", `<span class="arrow">${state.sort === th.dataset.sort ? (state.order === "asc" ? "▲" : "▼") : "↕"}</span>`);
      };
      update();
      th.addEventListener("click", () => {
        if (state.sort === th.dataset.sort) state.order = state.order === "asc" ? "desc" : "asc";
        else { state.sort = th.dataset.sort; state.order = th.dataset.default || "asc"; }
        $$("th[data-sort]", table).forEach((h) => { h.classList.remove("sorted"); h.querySelector(".arrow")?.remove();
          h.insertAdjacentHTML("beforeend", `<span class="arrow">${state.sort === h.dataset.sort ? (state.order === "asc" ? "▲" : "▼") : "↕"}</span>`);
          if (state.sort === h.dataset.sort) h.classList.add("sorted"); });
        onChange();
      });
    });
  }

  // ------------------------------------------------------------------ dropdown toggling
  function toggleDropdown(btn, menu, onOpen) {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = menu.classList.contains("hidden");
      $$(".topbar .dropdown").forEach((d) => d !== menu && d.classList.add("hidden"));
      menu.classList.toggle("hidden", !open);
      if (open && onOpen) onOpen();
    });
  }
  document.addEventListener("click", (e) => {
    $$(".topbar .dropdown").forEach((d) => { if (!d.contains(e.target)) d.classList.add("hidden"); });
  });

  // ------------------------------------------------------------------ chrome: sidebar, search, notifications, quick add
  function initChrome() {
    const sidebar = $("#sidebar"), scrim = $("#scrim");
    $("#menu-toggle")?.addEventListener("click", () => { sidebar.classList.add("open"); scrim.classList.add("open"); });
    scrim?.addEventListener("click", () => { sidebar.classList.remove("open"); scrim.classList.remove("open"); });

    // global search
    const input = $("#global-search-input"), results = $("#global-search-results");
    if (input) {
      const run = debounce(async () => {
        const term = input.value.trim();
        if (term.length < 2) { results.classList.add("hidden"); return; }
        results.innerHTML = loadingHTML; results.classList.remove("hidden");
        try {
          const r = await get("/api/search" + qs({ q: term }));
          const sec = (title, items, fn) => (items.length ? `<div class="group-label">${title}</div>${items.map(fn).join("")}` : "");
          const html = sec("Contacts", r.contacts, (c) => `<a class="item" href="/contacts/${c.contact_id}"><span class="avatar sm">${esc(initials(c.name))}</span><span><strong>${esc(c.name)}</strong><div class="small muted">${esc([c.email, c.phone, c.company].filter(Boolean).join(" · "))}</div></span></a>`)
            + sec("Companies", r.companies, (c) => `<a class="item" href="/companies/${c.company_id}"><span class="avatar sm company">${esc(initials(c.company_name))}</span><span><strong>${esc(c.company_name)}</strong><div class="small muted">${esc(c.industry || "")}</div></span></a>`)
            + sec("Leads", r.leads, (c) => `<a class="item" href="/contacts/${c.contact_id}"><span class="badge ${c.category}">${label(c.category)}</span><span>${esc(c.name)} <span class="muted small">score ${c.score}</span></span></a>`);
          results.innerHTML = html || `<div class="muted" style="padding:14px">No results for “${esc(term)}”.</div>`;
          results.insertAdjacentHTML("beforeend", `<div class="sep"></div><a class="item" href="/contacts?q=${encodeURIComponent(term)}">See all contacts matching “${esc(term)}” →</a>`);
        } catch (e) { results.innerHTML = errorHTML(e.message); }
      }, 220);
      input.addEventListener("input", run);
      input.addEventListener("focus", () => input.value.trim().length >= 2 && run());
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") location.href = `/contacts?q=${encodeURIComponent(input.value.trim())}`;
        if (e.key === "Escape") { results.classList.add("hidden"); input.blur(); }
      });
      document.addEventListener("click", (e) => { if (!$("#global-search").contains(e.target)) results.classList.add("hidden"); });
      document.addEventListener("keydown", (e) => {
        if (e.key === "/" && !/input|textarea|select/i.test(document.activeElement.tagName)) { e.preventDefault(); input.focus(); }
      });
    }

    // notifications
    const nBtn = $("#notif-btn"), nPanel = $("#notif-panel"), nDot = $("#notif-dot");
    async function loadNotifs(render) {
      try {
        const r = await get("/api/notifications");
        nDot.textContent = r.unread > 9 ? "9+" : r.unread; nDot.classList.toggle("hidden", !r.unread);
        if (!render) return;
        const icons = { import: ["📥", "#eff4ff"], error: ["⚠", "#fef2f2"], duplicates: ["⧉", "#fffbeb"], hot: ["🔥", "#fef2f2"] };
        nPanel.innerHTML = `<div class="notif-head"><strong>Notifications</strong><button class="link-btn small" id="notif-read">Mark all read</button></div>`
          + (r.items.length ? r.items.map((n) => `<a class="notif" href="${esc(n.link || "#")}"><span class="ico" style="background:${icons[n.type]?.[1] || "#f1f5f9"}">${icons[n.type]?.[0] || "•"}</span>
             <span><strong>${esc(n.title)}</strong><div class="small muted">${esc(n.body)}</div><div class="small muted">${fmtRelative(n.at)}</div></span></a>`).join("")
            : `<div class="empty" style="padding:28px"><p>You're all caught up.</p></div>`);
        $("#notif-read", nPanel)?.addEventListener("click", async (e) => {
          e.preventDefault(); e.stopPropagation(); await api("POST", "/api/notifications/read"); nDot.classList.add("hidden"); toast("Notifications marked as read.", "info");
        });
      } catch (e) { if (render) nPanel.innerHTML = errorHTML(e.message); }
    }
    if (nBtn) { toggleDropdown(nBtn, nPanel, () => { nPanel.innerHTML = loadingHTML; loadNotifs(true); }); loadNotifs(false); }

    refreshDupBadge();

    // profile + quick add
    toggleDropdown($("#profile-btn"), $("#profile-menu"));
    toggleDropdown($("#quick-add-btn"), $("#quick-add-menu"));
    $$("[data-quick]").forEach((b) => b.addEventListener("click", () => {
      $("#quick-add-menu").classList.add("hidden");
      ({ contact: () => contactForm(null), company: () => companyForm(null), activity: () => activityForm(null) })[b.dataset.quick]();
    }));
    $("#logout-btn")?.addEventListener("click", async () => {
      await api("POST", "/api/auth/logout", undefined, { allow401: true }).catch(() => {});
      location.href = "/login";
    });
  }

  function refreshDupBadge() {
    get("/api/duplicates?per_page=1").then((r) => {
      const b = $("#nav-dup-count"); if (!b) return;
      b.textContent = r.total; b.classList.toggle("hidden", !r.total);
    }).catch(() => {});
  }

  // ------------------------------------------------------------------ charts
  const charts = {};
  function chart(canvasId, config) {
    if (charts[canvasId]) charts[canvasId].destroy();
    const el = document.getElementById(canvasId); if (!el || !window.Chart) return null;
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = "#64748b";
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    charts[canvasId] = new Chart(el, config);
    return charts[canvasId];
  }
  const PALETTE = ["#2563eb", "#7c3aed", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#14b8a6", "#8b5cf6", "#ec4899", "#64748b", "#84cc16", "#f97316"];

  window.App = {
    api, get, qs, ApiError, esc, $, $$, fmtDate, fmtRelative, fmtNum, fmtMoney, initials, label, stageLabel, categoryBadge,
    scoreBar, debounce, download, toast, modal, confirmDialog, formData, field, selectField, showErrors, companyPicker,
    contactForm, companyForm, activityForm, renderPagination, bindSort, loadingHTML, emptyHTML, errorHTML, chart, PALETTE,
    CAT_COLORS, LIFECYCLE, STATUSES, refreshDupBadge,
  };
  document.addEventListener("DOMContentLoaded", initChrome);
})();
