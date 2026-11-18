/* Shared chart builders for Overview and Reports pages. */
(function () {
  const { chart, PALETTE, CAT_COLORS, label, stageLabel, fmtDate } = App;
  const tickFmt = (granularity) => (v) => {
    const d = new Date(v + "T00:00:00");
    return (granularity === "week" ? "Wk " : "") + d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  function leadsOverTime(id, data) {
    const t = data.leads_over_time;
    chart(id, {
      type: "line",
      data: { labels: t.labels.map(tickFmt(data.range.granularity)), datasets: [
        { label: "All leads", data: t.total, borderColor: "#2563eb", backgroundColor: "rgba(37,99,235,.08)", fill: true, cubicInterpolationMode: "monotone", pointRadius: 0, borderWidth: 2 },
        { label: "Hot", data: t.hot, borderColor: CAT_COLORS.hot, cubicInterpolationMode: "monotone", pointRadius: 0, borderWidth: 1.5 },
        { label: "Warm", data: t.warm, borderColor: CAT_COLORS.warm, cubicInterpolationMode: "monotone", pointRadius: 0, borderWidth: 1.5 },
        { label: "Cold", data: t.cold, borderColor: CAT_COLORS.cold, cubicInterpolationMode: "monotone", pointRadius: 0, borderWidth: 1.5, borderDash: [4, 3] },
      ] },
      options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef2f7" } }, x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } } },
        plugins: { legend: { position: "top", align: "end" } } },
    });
  }

  function distribution(id, dist) {
    const total = dist.hot + dist.warm + dist.cold;
    chart(id, {
      type: "doughnut",
      data: { labels: ["Hot", "Warm", "Cold"], datasets: [{ data: [dist.hot, dist.warm, dist.cold],
        backgroundColor: [CAT_COLORS.hot, CAT_COLORS.warm, "#94a3b8"], borderWidth: 2, borderColor: "#fff" }] },
      options: { maintainAspectRatio: false, cutout: "68%",
        plugins: { legend: { position: "bottom" },
          tooltip: { callbacks: { label: (c) => `${c.label}: ${c.raw} (${total ? Math.round(c.raw / total * 100) : 0}%)` } } },
        onClick: (_, els) => { if (els.length) location.href = `/leads?category=${["hot", "warm", "cold"][els[0].index]}`; } },
      plugins: [{ id: "center", afterDraw(c) {
        const { ctx, chartArea: a } = c; if (!a) return;
        ctx.save(); ctx.textAlign = "center"; ctx.fillStyle = "#0f1b33"; ctx.font = "700 24px " + Chart.defaults.font.family;
        ctx.fillText(total, (a.left + a.right) / 2, (a.top + a.bottom) / 2 + 4);
        ctx.font = "12px " + Chart.defaults.font.family; ctx.fillStyle = "#64748b";
        ctx.fillText("leads", (a.left + a.right) / 2, (a.top + a.bottom) / 2 + 22); ctx.restore();
      } }],
    });
  }

  function byCompany(id, d) {
    chart(id, {
      type: "bar",
      data: { labels: d.labels, datasets: [{ label: "Contacts", data: d.values, backgroundColor: "#2563eb", borderRadius: 5, maxBarThickness: 18 }] },
      options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef2f7" } }, y: { grid: { display: false } } } },
    });
  }

  function sources(id, d) {
    chart(id, {
      type: "doughnut",
      data: { labels: d.labels, datasets: [{ data: d.values, backgroundColor: PALETTE, borderWidth: 2, borderColor: "#fff" }] },
      options: { maintainAspectRatio: false, cutout: "55%", plugins: { legend: { position: "bottom" } } },
    });
  }

  function funnel(id, rows) {
    chart(id, {
      type: "bar",
      data: { labels: rows.map((r) => stageLabel(r.stage)), datasets: [{ label: "Reached stage", data: rows.map((r) => r.reached),
        backgroundColor: rows.map((_, i) => `rgba(37,99,235,${1 - i * 0.13})`), borderRadius: 5, maxBarThickness: 22 }] },
      options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false },
        tooltip: { callbacks: { afterLabel: (c) => `Currently in stage: ${rows[c.dataIndex].count}` } } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef2f7" } }, y: { grid: { display: false } } } },
    });
  }

  function imports(id, data) {
    const h = data.import_history;
    chart(id, {
      type: "bar",
      data: { labels: h.labels.map(tickFmt(h.granularity)), datasets: [
        { label: "Inserted", data: h.inserted, backgroundColor: "#2563eb", borderRadius: 4, stack: "s" },
        { label: "Updated", data: h.updated, backgroundColor: "#93c5fd", borderRadius: 4, stack: "s" },
        { label: "Failed rows", data: h.failed, backgroundColor: "#fca5a5", borderRadius: 4, stack: "s" },
      ] },
      options: { maintainAspectRatio: false, plugins: { legend: { position: "top", align: "end" } },
        scales: { y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef2f7" } }, x: { stacked: true, grid: { display: false }, ticks: { maxTicksLimit: 10 } } } },
    });
  }

  /** Range picker shared by dashboards. Calls onChange({range,start,end}). */
  function rangePicker(onChange) {
    const picker = document.getElementById("range-picker"), custom = document.getElementById("custom-range");
    const state = { range: "all" };
    picker.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-range]"); if (!b) return;
      picker.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      if (b.dataset.range === "custom") { custom.classList.remove("hidden"); return; }
      custom.classList.add("hidden");
      state.range = b.dataset.range; delete state.start; delete state.end;
      onChange({ ...state });
    });
    document.getElementById("apply-range").addEventListener("click", () => {
      const s = document.getElementById("range-start").value, e = document.getElementById("range-end").value;
      if (!s || !e) return App.toast("Choose both a start and an end date.", "error");
      if (s > e) return App.toast("The start date must be before the end date.", "error");
      Object.assign(state, { range: "custom", start: s, end: e });
      onChange({ ...state });
    });
    return state;
  }

  window.Analytics = { leadsOverTime, distribution, byCompany, sources, funnel, imports, rangePicker, fmtDate };
})();
