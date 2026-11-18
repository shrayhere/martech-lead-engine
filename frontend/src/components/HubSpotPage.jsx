import React, { useEffect, useState } from 'react';
import { Send, Eye, Loader2, KeyRound } from 'lucide-react';
import SourceSelect from './SourceSelect';

export default function HubSpotPage({ runs = [], defaultRunId = '' }) {
  const [runId, setRunId] = useState(defaultRunId || '');
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/hubspot/status').then((r) => r.json()).then(setStatus).catch(() => {});
  }, []);

  const sync = async (dryRun) => {
    if (!dryRun && !window.confirm('Push these contacts to your HubSpot portal now? Existing contacts with the same email are updated.')) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/hubspot/sync', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: runId || null, dry_run: dryRun }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setResult(body);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Send className="w-5 h-5 text-orange-400" /> HubSpot Sync
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Upserts clean, scored, classified leads into HubSpot contacts by email. Junk and email-less leads are never sent.
          </p>
        </div>
        <SourceSelect runs={runs} value={runId} onChange={setRunId} />
      </div>

      <div className="glass-panel p-5 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3 text-sm">
          <KeyRound className={`w-5 h-5 ${status?.token_configured ? 'text-emerald-400' : 'text-slate-500'}`} />
          {status?.token_configured
            ? <span className="text-emerald-300">HubSpot token is set on the server.</span>
            : <span className="text-slate-300">No HubSpot token on the server: preview works, push is disabled. See <code className="text-indigo-300">docs/hubspot_setup.md</code>.</span>}
        </div>
        <div className="flex gap-2">
          <button onClick={() => sync(true)} disabled={busy}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-sm font-semibold disabled:opacity-50">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />} Preview (dry run)
          </button>
          <button onClick={() => sync(false)} disabled={busy || !status?.token_configured}
            className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-xl text-sm font-bold disabled:opacity-40">
            <Send className="w-4 h-4" /> Push to HubSpot
          </button>
        </div>
      </div>

      {error && <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm">{error}</div>}

      {result && (
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><div className="text-[11px] text-slate-400 uppercase">Mode</div><div className="font-bold text-white">{result.dry_run ? 'Dry run (nothing sent)' : 'Pushed'}</div></div>
            <div><div className="text-[11px] text-slate-400 uppercase">Contacts selected</div><div className="font-bold text-white">{result.contacts_selected}</div></div>
            <div><div className="text-[11px] text-slate-400 uppercase">API calls</div><div className="font-bold text-white">{result.batches} × batch upsert</div></div>
            <div><div className="text-[11px] text-slate-400 uppercase">{result.dry_run ? 'Unscored / unclassified' : 'Upserted'}</div>
              <div className="font-bold text-white">{result.dry_run ? result.unscored_or_unclassified : result.contacts_upserted}</div></div>
          </div>
          {result.errors?.length > 0 && (
            <div className="text-xs text-rose-300">{result.errors.length} errors: {result.errors.slice(0, 3).map((e) => e.message).join(' | ')}</div>
          )}
          {result.preview && (
            <div>
              <h3 className="text-sm font-semibold text-white mb-2">First {result.preview.length} payloads</h3>
              <pre className="text-[11px] bg-slate-950 border border-slate-800 rounded-xl p-4 overflow-x-auto text-slate-300 max-h-96">
                {JSON.stringify(result.preview, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
