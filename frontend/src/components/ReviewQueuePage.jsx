import React, { useCallback, useEffect, useState } from 'react';
import { ClipboardCheck, Check, X, Loader2, GitMerge, Trash2 } from 'lucide-react';
import SourceSelect from './SourceSelect';
import { withRun } from '../apiUtils';

function Record({ r }) {
  if (!r) return null;
  return (
    <div className="text-xs text-slate-300 space-y-0.5">
      <div className="font-semibold text-white">{`${r.first_name || ''} ${r.last_name || ''}`.trim() || '(no name)'}</div>
      <div>{r.company || '—'}{r.job_title ? ` · ${r.job_title}` : ''}</div>
      <div className="font-mono text-slate-400">{r.email || 'no email'} · {r.phone || 'no phone'}</div>
    </div>
  );
}

export default function ReviewQueuePage({ runs = [], defaultRunId = '' }) {
  const [runId, setRunId] = useState(defaultRunId || '');
  const [status, setStatus] = useState('pending');
  const [data, setData] = useState({ summary: null, items: [] });
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(withRun(`/api/review?status=${status}`, runId));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(`Could not load the review queue: ${e.message}`);
    }
  }, [runId, status]);

  useEffect(() => { load(); }, [load]);

  const decide = async (id, decision) => {
    setBusy(id);
    setError(null);
    try {
      const res = await fetch(`/api/review/${id}/${decision}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const s = data.summary;

  return (
    <div className="space-y-6">
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-indigo-400" /> Needs Review
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Borderline duplicate pairs (80–90% similarity) are not merged automatically, and junk rows are not dropped
            silently: a person decides here.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SourceSelect runs={runs} value={runId} onChange={setRunId} />
          <select value={status} onChange={(e) => setStatus(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200 text-xs">
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="all">All</option>
          </select>
        </div>
      </div>

      {s && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[['Pending merges', s.merge_pending, 'text-indigo-300'], ['Pending junk', s.junk_pending, 'text-amber-300'],
            ['Approved', s.approved, 'text-emerald-300'], ['Rejected', s.rejected, 'text-rose-300']].map(([l, v, c]) => (
            <div key={l} className="glass-panel p-4 rounded-2xl">
              <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">{l}</span>
              <div className={`text-2xl font-extrabold ${c}`}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm">{error}</div>}

      <div className="space-y-3">
        {data.items.length === 0 && (
          <div className="glass-panel p-6 rounded-2xl text-sm text-slate-400">
            Nothing here. {status === 'pending' ? 'Run cleaning or a Smart Upload to fill the queue.' : ''}
          </div>
        )}
        {data.items.map((item) => (
          <div key={item.id} className="glass-panel p-4 rounded-2xl flex flex-col lg:flex-row gap-4 lg:items-center">
            <div className="flex items-center gap-2 lg:w-40 shrink-0">
              {item.item_type === 'merge'
                ? <GitMerge className="w-4 h-4 text-indigo-400" />
                : <Trash2 className="w-4 h-4 text-amber-400" />}
              <span className="text-xs font-bold text-white uppercase">
                {item.item_type === 'merge' ? 'Possible duplicate' : 'Junk?'}
              </span>
            </div>
            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
              <Record r={item.record_a} />
              {item.item_type === 'merge' ? <Record r={item.record_b} /> : (
                <div className="text-xs text-amber-200/80">{item.reason}</div>
              )}
            </div>
            <div className="lg:w-56 text-xs text-slate-400">
              {item.item_type === 'merge' && (
                <div className="font-mono text-indigo-300 mb-1">Similarity {item.similarity_score}%</div>
              )}
              {item.status !== 'pending' ? (
                <span className={item.status === 'approved' ? 'text-emerald-300' : 'text-rose-300'}>
                  {item.status}: {item.resolution_note}
                </span>
              ) : (
                <div className="flex gap-2">
                  <button disabled={busy === item.id} onClick={() => decide(item.id, 'approve')}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold disabled:opacity-50">
                    {busy === item.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                    {item.item_type === 'merge' ? 'Merge' : 'Is junk'}
                  </button>
                  <button disabled={busy === item.id} onClick={() => decide(item.id, 'reject')}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white font-semibold disabled:opacity-50">
                    <X className="w-3 h-3" /> {item.item_type === 'merge' ? 'Keep both' : 'Not junk'}
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
