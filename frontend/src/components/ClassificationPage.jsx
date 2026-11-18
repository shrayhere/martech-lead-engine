import React, { useCallback, useEffect, useState } from 'react';
import { Brain, Play, Loader2 } from 'lucide-react';
import SourceSelect from './SourceSelect';
import { withRun } from '../apiUtils';

const ROLE_COLORS = {
  'Decision Maker': 'text-rose-300', Influencer: 'text-amber-300', 'End User': 'text-cyan-300', Unknown: 'text-slate-500',
};

export default function ClassificationPage({ runs = [], defaultRunId = '' }) {
  const [runId, setRunId] = useState(defaultRunId || '');
  const [engine, setEngine] = useState('local');
  const [status, setStatus] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [leads, setLeads] = useState([]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const loadLeads = useCallback(async () => {
    try {
      const res = await fetch(withRun('/api/classify/leads?limit=300', runId));
      if (res.ok) setLeads((await res.json()).leads);
    } catch (e) {
      setError(e.message);
    }
  }, [runId]);

  useEffect(() => {
    fetch('/api/classify/status').then((r) => r.json()).then(setStatus).catch(() => {});
    fetch('/api/classify/accuracy').then((r) => r.json()).then(setAccuracy).catch(() => {});
  }, []);
  useEffect(() => { loadLeads(); }, [loadLeads]);

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch(withRun(`/api/classify/run?engine=${engine}`, runId), { method: 'POST' });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setResult(body);
      await loadLeads();
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const classified = leads.filter((l) => l.persona);

  return (
    <div className="space-y-6">
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Brain className="w-5 h-5 text-fuchsia-400" /> AI Classification
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Labels persona, buying role and interest from the job title, then business rules pick the next action
            using the role and the score band.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <SourceSelect runs={runs} value={runId} onChange={setRunId} />
          <select value={engine} onChange={(e) => setEngine(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200 text-xs">
            <option value="local">Local model (free)</option>
            <option value="claude" disabled={!status?.claude}>
              Claude {status?.claude ? `(${status.claude_model})` : '(needs ANTHROPIC_API_KEY)'}
            </option>
          </select>
          <button onClick={run} disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-bold disabled:opacity-50">
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Classify leads
          </button>
        </div>
      </div>

      {error && <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass-panel p-5 rounded-2xl">
          <h3 className="text-sm font-semibold text-white mb-3">Accuracy on held-out titles (local model)</h3>
          {accuracy ? (
            <>
              <table className="w-full text-xs">
                <tbody>
                  {['persona', 'buying_role', 'interest'].map((t) => (
                    <tr key={t} className="border-b border-slate-900">
                      <td className="py-1.5 text-slate-300">{t}</td>
                      <td className="py-1.5 text-right font-mono text-emerald-300">{accuracy.accuracy_pct[t]}%</td>
                    </tr>
                  ))}
                  <tr><td className="py-1.5 text-slate-300">all three correct</td>
                    <td className="py-1.5 text-right font-mono text-emerald-300">{accuracy.all_three_correct_pct}%</td></tr>
                </tbody>
              </table>
              <p className="text-[11px] text-slate-500 mt-2">
                {accuracy.test_titles} test titles not seen in training ({accuracy.train_titles} titles). Hand-labelled
                benchmark: it checks the model follows the label definitions, not that labels predict purchases.
              </p>
            </>
          ) : <p className="text-xs text-slate-500">Loading…</p>}
        </div>

        <div className="glass-panel p-5 rounded-2xl lg:col-span-2">
          <h3 className="text-sm font-semibold text-white mb-3">Recommended actions</h3>
          {result ? (
            <ul className="space-y-1.5 text-xs">
              {Object.entries(result.actions).slice(0, 8).map(([a, n]) => (
                <li key={a} className="flex justify-between gap-4">
                  <span className="text-slate-300">{a}</span><span className="font-mono text-indigo-300">{n}</span>
                </li>
              ))}
              <li className="text-slate-500 pt-1">Engines used: {Object.entries(result.engines_used).map(([k, v]) => `${k} ${v}`).join(', ')}</li>
            </ul>
          ) : (
            <p className="text-xs text-slate-500">
              {classified.length ? `${classified.length} leads already classified. Click "Classify leads" to re-run.`
                : 'Click "Classify leads" to label the leads.'}
            </p>
          )}
        </div>
      </div>

      <div className="glass-panel p-6 rounded-2xl overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400 border-b border-slate-800 text-left [&>th]:pr-3">
              <th className="py-2">Lead</th><th>Job title</th><th>Band</th><th>Persona</th><th>Buying role</th>
              <th>Interest</th><th className="text-right">Conf.</th><th>Next action</th>
            </tr>
          </thead>
          <tbody>
            {classified.slice(0, 150).map((l) => (
              <tr key={l.id} className="border-b border-slate-900 align-top [&>td]:pr-3">
                <td className="py-2 text-white">{l.name}<div className="text-slate-500">{l.company}</div></td>
                <td className="py-2 text-slate-300">{l.job_title || '—'}</td>
                <td className="py-2 text-slate-300">{l.is_junk ? 'Junk' : (l.score_band || '—')}</td>
                <td className="py-2 text-slate-200">{l.persona}</td>
                <td className={`py-2 font-semibold ${ROLE_COLORS[l.buying_role] || ''}`}>{l.buying_role}</td>
                <td className="py-2 text-slate-300">{l.interest}</td>
                <td className="py-2 text-right font-mono text-slate-400">
                  {l.confidence === null || l.confidence === undefined ? l.engine : `${Math.round(l.confidence * 100)}%`}
                </td>
                <td className="py-2 text-slate-300 max-w-xs">{l.recommended_action}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {classified.length === 0 && <p className="text-xs text-slate-500 py-4">No classified leads for this source yet.</p>}
      </div>
    </div>
  );
}
