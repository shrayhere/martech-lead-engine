import React from 'react';

// Picks which data the page works on: the staged flow (Stages 1-4) or one Smart Upload run.
// value '' = staged flow; otherwise a run_id.
export default function SourceSelect({ runs = [], value, onChange }) {
  return (
    <label className="flex items-center gap-2 text-xs text-slate-400">
      <span className="font-semibold uppercase tracking-wider">Data</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200 text-xs max-w-xs"
      >
        <option value="">Staged flow (Stages 1–4)</option>
        {runs.map((r) => (
          <option key={r.run_id} value={r.run_id}>
            Smart run: {r.filename} ({r.run_id.slice(0, 8)})
          </option>
        ))}
      </select>
    </label>
  );
}

