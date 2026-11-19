import React, { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw, Send, Eye, Loader2, KeyRound, CheckCircle2, AlertTriangle,
  XCircle, Clock, Zap, Database, Shield, ChevronDown, ChevronUp,
  ArrowDownFromLine, ArrowUpFromLine, Info, ToggleLeft, ToggleRight
} from 'lucide-react';
import SourceSelect from './SourceSelect';

// ─── helpers ────────────────────────────────────────────────────────────────
const fmt = (d) => d ? new Date(d).toLocaleString() : '—';
const ago = (d) => {
  if (!d) return 'never';
  const s = Math.round((Date.now() - new Date(d)) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
};

const StatusBadge = ({ status }) => {
  const map = {
    ok: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    error: 'bg-red-500/15 text-red-300 border-red-500/30',
    ACTIVE: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    INACTIVE: 'bg-slate-700/50 text-slate-400 border-slate-600/30',
    DRAFT: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  };
  const cls = map[status] || 'bg-slate-700/50 text-slate-400 border-slate-600/30';
  return (
    <span className={`px-2 py-0.5 text-[11px] font-semibold rounded-full border ${cls}`}>
      {status}
    </span>
  );
};

// ─── Scope list component ────────────────────────────────────────────────────
function ScopeList({ scopes }) {
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {scopes.map(s => (
        <code key={s} className="px-2 py-0.5 bg-slate-800 text-indigo-300 text-[11px] rounded border border-slate-700">
          {s}
        </code>
      ))}
    </div>
  );
}

// ─── Workflow row ────────────────────────────────────────────────────────────
function WorkflowRow({ wf }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-[#1F2937] rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#121826] hover:bg-slate-800/60 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          {wf.mapped
            ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            : <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />}
          <span className="font-medium text-sm text-[#E5E7EB] truncate">{wf.name}</span>
          <StatusBadge status={wf.status} />
          {wf.trigger_type && (
            <span className="hidden md:inline text-[11px] text-[#9CA3AF] bg-slate-800 px-1.5 py-0.5 rounded">
              {wf.trigger_type}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <span className="text-[11px] text-[#9CA3AF]">{ago(wf.synced_at)}</span>
          {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>
      </button>
      {open && (
        <div className="px-4 py-3 bg-[#0B0F1A] border-t border-[#1F2937] text-sm space-y-2">
          <div><span className="text-[#9CA3AF]">Trigger: </span><span className="text-[#E5E7EB]">{wf.trigger_summary}</span></div>
          <div><span className="text-[#9CA3AF]">Actions: </span><span className="text-[#E5E7EB]">{wf.action_count}</span></div>
          {wf.mapped
            ? <div className="text-emerald-400 text-xs">✓ Converted to scoring rule(s)</div>
            : <div className="text-amber-400 text-xs">Not mapped: {wf.not_mapped_reason}</div>}
        </div>
      )}
    </div>
  );
}

// ─── Scoring rule row ────────────────────────────────────────────────────────
function RuleRow({ rule, onToggle }) {
  const delta = rule.score_delta;
  const color = rule.rule_type === 'score_boost'
    ? 'text-emerald-400' : rule.rule_type === 'score_penalty'
    ? 'text-red-400' : 'text-indigo-400';
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-[#121826] border border-[#1F2937] rounded-xl text-sm">
      <button
        onClick={() => onToggle(rule.id, !rule.active)}
        className="shrink-0 text-slate-400 hover:text-indigo-400 transition-colors"
        title={rule.active ? 'Disable rule' : 'Enable rule'}
      >
        {rule.active ? <ToggleRight className="w-5 h-5 text-indigo-400" /> : <ToggleLeft className="w-5 h-5" />}
      </button>
      <span className={`font-mono font-bold w-12 text-right shrink-0 ${color}`}>
        {delta > 0 ? `+${delta}` : delta}
      </span>
      <span className="text-[#9CA3AF] text-xs shrink-0 w-28 truncate">{rule.trigger_type}</span>
      <span className="text-[#E5E7EB] truncate flex-1">{rule.description}</span>
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────
export default function HubSpotPage({ runs = [] }) {
  const [status, setStatus] = useState(null);
  const [workflows, setWorkflows] = useState([]);
  const [rules, setRules] = useState([]);
  const [syncLog, setSyncLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [pushDry, setPushDry] = useState(true);
  const [pushResult, setPushResult] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview'); // overview | workflows | rules | push | log
  const [runId, setRunId] = useState('');
  const [wfFilter, setWfFilter] = useState('all'); // all | mapped | not_mapped

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sRes, wRes, rRes, lRes] = await Promise.all([
        fetch('/api/hubspot/status'),
        fetch('/api/hubspot/workflows?limit=200'),
        fetch('/api/hubspot/rules?active_only=false'),
        fetch('/api/hubspot/sync-log?limit=20'),
      ]);
      if (sRes.ok) setStatus(await sRes.json());
      if (wRes.ok) { const d = await wRes.json(); setWorkflows(d.workflows || []); }
      if (rRes.ok) { const d = await rRes.json(); setRules(d.rules || []); }
      if (lRes.ok) { const d = await lRes.json(); setSyncLog(d.logs || []); }
    } catch (e) {
      setError('Could not load HubSpot data: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 30s while import is running
  useEffect(() => {
    if (!importing) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [importing, load]);

  const handleImport = async () => {
    setImporting(true);
    setError(null);
    setImportResult(null);
    try {
      const res = await fetch('/api/hubspot/import-workflows', { method: 'POST' });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setImportResult(body);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setImporting(false);
    }
  };

  const handlePush = async () => {
    if (!pushDry && !window.confirm('Push scored leads to your HubSpot portal? Existing contacts will be updated.')) return;
    setPushing(true);
    setError(null);
    setPushResult(null);
    try {
      const res = await fetch('/api/hubspot/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: runId || null, dry_run: pushDry }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setPushResult(body);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setPushing(false);
    }
  };

  const handleToggleRule = async (ruleId, active) => {
    await fetch('/api/hubspot/rules/toggle', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rule_ids: [ruleId], active }),
    });
    await load();
  };

  const tokenOk = status?.token_configured;
  const filteredWf = wfFilter === 'mapped'
    ? workflows.filter(w => w.mapped)
    : wfFilter === 'not_mapped'
    ? workflows.filter(w => !w.mapped)
    : workflows;

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'workflows', label: `Workflows (${workflows.length})` },
    { id: 'rules', label: `Scoring Rules (${rules.length})` },
    { id: 'push', label: 'Push to HubSpot' },
    { id: 'log', label: 'Sync Log' },
  ];

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center py-24 text-[#9CA3AF]">
        <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading HubSpot data…
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header card */}
      <div className="bg-[#121826] border border-[#1F2937] rounded-xl p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Database className="w-5 h-5 text-[#6366F1]" /> HubSpot Integration
            </h2>
            <p className="text-sm text-[#9CA3AF] mt-1">
              Import workflows from HubSpot to drive lead scoring rules, then push scored leads back.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm ${tokenOk ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-slate-800 border-slate-700 text-[#9CA3AF]'}`}>
              <KeyRound className="w-4 h-4" />
              {tokenOk ? 'Token connected' : 'No token'}
            </div>
            <button
              onClick={load}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-[#1F2937] rounded-lg text-sm text-[#E5E7EB] transition-colors"
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>

        {/* Quick stats */}
        {status && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
            {[
              { label: 'Workflows imported', val: status.workflows_in_db ?? 0, color: 'text-[#6366F1]' },
              { label: 'Mapped to rules', val: status.workflows_mapped ?? 0, color: 'text-[#2DD4BF]' },
              { label: 'Active scoring rules', val: status.active_scoring_rules ?? 0, color: 'text-emerald-400' },
              { label: 'Last import', val: status.last_import?.synced_at ? ago(status.last_import.synced_at) : 'never', color: 'text-[#9CA3AF]' },
            ].map(({ label, val, color }) => (
              <div key={label} className="bg-[#0B0F1A] border border-[#1F2937] rounded-lg p-3">
                <div className="text-[11px] text-[#9CA3AF] uppercase tracking-wide">{label}</div>
                <div className={`text-lg font-bold font-mono mt-0.5 ${color}`}>{val}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Token setup instructions if not configured */}
      {!tokenOk && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex gap-3">
          <Info className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-sm">
            <div className="font-semibold text-amber-300 mb-1">HubSpot token not configured</div>
            <p className="text-[#9CA3AF] mb-2">
              Set the <code className="text-amber-300 bg-slate-900 px-1 rounded">HUBSPOT_ACCESS_TOKEN</code> environment
              variable on your backend. Create a Private App in HubSpot with these scopes:
            </p>
            <ScopeList scopes={status?.required_scopes || []} />
            <p className="text-[#9CA3AF] mt-2 text-xs">
              See <code>docs/hubspot_setup.md</code> for step-by-step instructions.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 text-red-300 text-sm flex items-start gap-2">
          <XCircle className="w-4 h-4 shrink-0 mt-0.5" /> {error}
        </div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-1 flex-wrap">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border ${activeTab === t.id
              ? 'bg-[#6366F1]/20 text-indigo-300 border-[#6366F1]/40'
              : 'bg-[#121826] border-[#1F2937] text-[#9CA3AF] hover:text-[#E5E7EB]'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Overview tab ── */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          {/* Import Workflows CTA */}
          <div className="bg-[#121826] border border-[#1F2937] rounded-xl p-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 className="font-semibold text-[#E5E7EB] flex items-center gap-2">
                  <ArrowDownFromLine className="w-4 h-4 text-[#2DD4BF]" /> Import Workflows from HubSpot
                </h3>
                <p className="text-sm text-[#9CA3AF] mt-1">
                  Reads your HubSpot automation workflows via the Automation v4 API and converts
                  enrollment triggers into lead scoring rules.
                </p>
                {status?.last_import && (
                  <p className="text-xs text-[#9CA3AF] mt-1">
                    Last import: <span className="text-[#E5E7EB]">{fmt(status.last_import.synced_at)}</span>
                    {' · '}{status.last_import.workflows_found ?? 0} found,{' '}
                    {status.last_import.workflows_mapped ?? 0} mapped,{' '}
                    {status.last_import.rules_created ?? 0} rules created
                    {status.last_import.error && (
                      <span className="text-red-400"> · Error: {status.last_import.error}</span>
                    )}
                  </p>
                )}
              </div>
              <button
                onClick={handleImport}
                disabled={importing || !tokenOk}
                className="flex items-center gap-2 px-5 py-2.5 bg-[#6366F1] hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold disabled:opacity-40 transition-colors shrink-0"
              >
                {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                {importing ? 'Importing…' : 'Sync Now'}
              </button>
            </div>
            {importResult && (
              <div className="mt-4 bg-[#0B0F1A] border border-[#1F2937] rounded-lg p-4 text-sm space-y-2">
                <div className="font-semibold text-[#E5E7EB]">Import complete</div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { l: 'Found', v: importResult.workflows_found },
                    { l: 'Mapped', v: importResult.workflows_mapped },
                    { l: 'Not mapped', v: importResult.workflows_not_mapped },
                    { l: 'Rules created', v: importResult.rules_created },
                  ].map(({ l, v }) => (
                    <div key={l}><div className="text-[11px] text-[#9CA3AF]">{l}</div><div className="font-bold font-mono text-[#E5E7EB]">{v ?? 0}</div></div>
                  ))}
                </div>
                {importResult.not_mapped_list?.length > 0 && (
                  <div>
                    <div className="text-amber-400 text-xs font-semibold mb-1">Not mapped workflows:</div>
                    <ul className="space-y-0.5">
                      {importResult.not_mapped_list.map(wf => (
                        <li key={wf.id} className="text-xs text-[#9CA3AF]">
                          <span className="text-[#E5E7EB]">{wf.name}</span> — {wf.reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {importResult.errors?.length > 0 && (
                  <div className="text-red-400 text-xs">{importResult.errors.join(' | ')}</div>
                )}
              </div>
            )}
          </div>

          {/* Background sync info */}
          <div className="bg-[#121826] border border-[#1F2937] rounded-xl p-4 flex gap-3 text-sm">
            <Clock className="w-4 h-4 text-[#9CA3AF] shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-[#E5E7EB]">Background sync</div>
              <div className="text-[#9CA3AF] text-xs mt-0.5">
                The server automatically re-imports workflows every hour (configurable via{' '}
                <code className="text-indigo-300">HUBSPOT_SYNC_INTERVAL_HOURS</code> env var).
                Webhooks on <code className="text-indigo-300">/api/hubspot/webhook</code> handle
                real-time contact and deal updates.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Workflows tab ── */}
      {activeTab === 'workflows' && (
        <div className="space-y-3">
          {workflows.length === 0 ? (
            <div className="text-center py-16 text-[#9CA3AF]">
              <Database className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="font-medium">No workflows imported yet</p>
              <p className="text-sm mt-1">Click "Sync Now" in the Overview tab to import from HubSpot.</p>
            </div>
          ) : (
            <>
              <div className="flex gap-2 items-center">
                {['all', 'mapped', 'not_mapped'].map(f => (
                  <button
                    key={f}
                    onClick={() => setWfFilter(f)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${wfFilter === f
                      ? 'bg-[#6366F1]/20 border-[#6366F1]/40 text-indigo-300'
                      : 'bg-[#121826] border-[#1F2937] text-[#9CA3AF] hover:text-[#E5E7EB]'}`}
                  >
                    {f === 'all' ? `All (${workflows.length})` : f === 'mapped' ? `Mapped (${workflows.filter(w => w.mapped).length})` : `Not mapped (${workflows.filter(w => !w.mapped).length})`}
                  </button>
                ))}
              </div>
              <div className="space-y-2">
                {filteredWf.map(wf => <WorkflowRow key={wf.hubspot_id} wf={wf} />)}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Rules tab ── */}
      {activeTab === 'rules' && (
        <div className="space-y-2">
          {rules.length === 0 ? (
            <div className="text-center py-16 text-[#9CA3AF]">
              <Shield className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="font-medium">No scoring rules yet</p>
              <p className="text-sm mt-1">Import workflows first. Supported triggers will auto-generate rules.</p>
            </div>
          ) : (
            <>
              <p className="text-xs text-[#9CA3AF]">
                These rules are applied on top of firmographic scoring during the pipeline. Toggle any rule off to disable it without deleting it.
              </p>
              <div className="space-y-1.5">
                {rules.map(r => <RuleRow key={r.id} rule={r} onToggle={handleToggleRule} />)}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Push tab ── */}
      {activeTab === 'push' && (
        <div className="space-y-4">
          <div className="bg-[#121826] border border-[#1F2937] rounded-xl p-5">
            <h3 className="font-semibold text-[#E5E7EB] flex items-center gap-2 mb-3">
              <ArrowUpFromLine className="w-4 h-4 text-[#F97316]" /> Push scored leads to HubSpot
            </h3>
            <p className="text-sm text-[#9CA3AF] mb-4">
              Upserts clean, scored, classified leads as HubSpot contacts (by email).
              Junk and email-less leads are never sent.
            </p>
            <div className="flex flex-col md:flex-row gap-3 items-start md:items-center">
              <SourceSelect runs={runs} value={runId} onChange={setRunId} />
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 text-sm text-[#9CA3AF] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pushDry}
                    onChange={e => setPushDry(e.target.checked)}
                    className="accent-indigo-500 w-4 h-4"
                  />
                  Dry run (preview only)
                </label>
              </div>
              <button
                onClick={handlePush}
                disabled={pushing || (!pushDry && !tokenOk)}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-40 transition-colors ${pushDry
                  ? 'bg-slate-700 hover:bg-slate-600 text-white'
                  : 'bg-[#F97316] hover:bg-orange-500 text-white'}`}
              >
                {pushing ? <Loader2 className="w-4 h-4 animate-spin" /> : pushDry ? <Eye className="w-4 h-4" /> : <Send className="w-4 h-4" />}
                {pushing ? 'Working…' : pushDry ? 'Preview' : 'Push to HubSpot'}
              </button>
            </div>

            {pushResult && (
              <div className="mt-4 bg-[#0B0F1A] border border-[#1F2937] rounded-lg p-4 space-y-3 text-sm">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div><div className="text-[11px] text-[#9CA3AF]">Mode</div><div className="font-bold text-[#E5E7EB]">{pushResult.dry_run ? 'Dry run' : 'Live push'}</div></div>
                  <div><div className="text-[11px] text-[#9CA3AF]">Selected</div><div className="font-bold font-mono text-[#E5E7EB]">{pushResult.contacts_selected}</div></div>
                  <div><div className="text-[11px] text-[#9CA3AF]">Batches</div><div className="font-bold font-mono text-[#E5E7EB]">{pushResult.batches}</div></div>
                  <div><div className="text-[11px] text-[#9CA3AF]">{pushResult.dry_run ? 'Unscored' : 'Upserted'}</div><div className="font-bold font-mono text-[#E5E7EB]">{pushResult.dry_run ? pushResult.unscored_or_unclassified : pushResult.contacts_upserted}</div></div>
                </div>
                {pushResult.skipped_invalid_email > 0 && (
                  <div className="text-amber-300 text-xs">
                    Skipped {pushResult.skipped_invalid_email} invalid email(s): {pushResult.skipped_invalid_email_examples?.join(', ')}
                  </div>
                )}
                {pushResult.errors?.length > 0 && (
                  <div className="text-red-400 text-xs">{pushResult.errors.length} error(s): {pushResult.errors.slice(0, 3).map(e => e.message).join(' | ')}</div>
                )}
                {pushResult.preview && (
                  <div>
                    <div className="text-xs font-semibold text-[#9CA3AF] mb-1">Preview (first {pushResult.preview.length})</div>
                    <pre className="text-[10px] bg-[#0B0F1A] border border-[#1F2937] rounded-lg p-3 overflow-x-auto text-[#9CA3AF] max-h-64">
                      {JSON.stringify(pushResult.preview, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Log tab ── */}
      {activeTab === 'log' && (
        <div className="space-y-2">
          {syncLog.length === 0 ? (
            <div className="text-center py-16 text-[#9CA3AF]">
              <Clock className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>No sync history yet</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-[#9CA3AF] uppercase border-b border-[#1F2937]">
                    <th className="text-left pb-2 pr-4">Time</th>
                    <th className="text-left pb-2 pr-4">Direction</th>
                    <th className="text-left pb-2 pr-4">Status</th>
                    <th className="text-left pb-2 pr-4">Triggered by</th>
                    <th className="text-left pb-2 pr-4">Workflows</th>
                    <th className="text-left pb-2 pr-4">Rules</th>
                    <th className="text-left pb-2">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {syncLog.map(l => (
                    <tr key={l.id} className="border-b border-[#1F2937]/50 hover:bg-[#121826] transition-colors">
                      <td className="py-2 pr-4 text-[#9CA3AF] whitespace-nowrap text-xs">{fmt(l.synced_at)}</td>
                      <td className="py-2 pr-4">
                        <span className={`flex items-center gap-1 ${l.direction === 'import' ? 'text-indigo-400' : 'text-orange-400'}`}>
                          {l.direction === 'import' ? <ArrowDownFromLine className="w-3 h-3" /> : <ArrowUpFromLine className="w-3 h-3" />}
                          {l.direction}
                        </span>
                      </td>
                      <td className="py-2 pr-4"><StatusBadge status={l.status} /></td>
                      <td className="py-2 pr-4 text-[#9CA3AF] text-xs">{l.triggered_by || '—'}</td>
                      <td className="py-2 pr-4 font-mono text-[#E5E7EB]">{l.workflows_found ?? '—'}/{l.workflows_mapped ?? '—'}</td>
                      <td className="py-2 pr-4 font-mono text-[#E5E7EB]">{l.rules_created ?? '—'}</td>
                      <td className="py-2 text-red-400 text-xs max-w-xs truncate">{l.error_message || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
