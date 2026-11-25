import React, { useCallback, useEffect, useState } from 'react';
import { Gauge, AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import SourceSelect from './SourceSelect';
import { withRun } from '../apiUtils';

const CHECKS = [
  ['valid_email', 'Valid email'],
  ['phone_e164', 'Phone in E.164 format'],
  ['state_standard', '2-letter US state'],
  ['has_job_title', 'Job title present'],
  ['has_company', 'Company present'],
  ['has_industry', 'Industry present'],
  ['not_duplicate', 'Not an exact duplicate'],
  ['not_junk', 'Not junk'],
  ['has_country', 'Country present (not scored)'],
  ['has_owner', 'Owner assigned (not scored)'],
];

const fmt = (v) => (v === null || v === undefined ? '—' : `${v}%`);

function ScoreCard({ title, side, accent }) {
  return (
    <div className={`glass-panel p-5 rounded-2xl border-l-4 ${accent}`}>
      <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">{title}</span>
      <div className="text-3xl font-extrabold text-white mt-1">{side ? `${side.score}` : '—'}</div>
      <p className="text-[11px] text-slate-400 mt-1">
        {side ? `${side.total_records} records` : 'No data yet'}
      </p>
    </div>
  );
}

function IssueList({ title, side }) {
  return (
    <div className="glass-panel p-5 rounded-2xl">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
        <AlertTriangle className="w-4 h-4 text-amber-400" /> {title}
      </h3>
      {!side || side.top_issues.length === 0 ? (
        <p className="text-xs text-slate-500">{side ? 'No issues found.' : 'No data yet.'}</p>
      ) : (
        <ol className="space-y-2">
          {side.top_issues.map((i, k) => (
            <li key={i.issue} className="flex items-center justify-between text-xs">
              <span className="text-slate-300">{k + 1}. {i.issue}</span>
              <span className="text-amber-300 font-mono">{i.records} ({i.pct}%)</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default function QualityScorePage({ runs = [], defaultRunId = '' }) {
  const initialRunId = defaultRunId || (runs && runs.length > 0 ? runs[0].run_id : '');
  const [runId, setRunId] = useState(initialRunId);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!runId && runs && runs.length > 0) {
      setRunId(runs[0].run_id);
    }
  }, [runs, runId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(withRun('/api/quality/report', runId));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setReport(await res.json());
    } catch (e) {
      setError(`Could not load the quality report: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => { load(); }, [load]);

  const before = report?.before;
  const after = report?.after;

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 border border-white/10">
        <div>
          <h2 className="text-2xl font-normal text-[#f3f6f2] flex items-center gap-2">
            <span className="font-display text-[#e6ecc9]">Data quality</span> health scores
          </h2>
          <p className="text-xs text-[#c9d6d3] mt-1">
            Measured before cleaning (as uploaded) and after (active clean leads). Score = average pass rate of 8 checks.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SourceSelect runs={runs} value={runId} onChange={setRunId} />
          <button onClick={load} className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300" title="Refresh">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {error && <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm">{error}</div>}

      {report && !before && !after && (
        <div className="p-4 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-300 text-sm">
          No data for this source yet. Upload and clean leads (Stages 1–2) or run a Smart Upload first.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ScoreCard title="Score before cleaning" side={before} accent="border-l-rose-500" />
        <ScoreCard title="Score after cleaning" side={after} accent="border-l-emerald-500" />
        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-indigo-500">
          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Change</span>
          <div className="text-3xl font-extrabold text-indigo-300 mt-1">
            {report?.score_improvement === null || report?.score_improvement === undefined
              ? '—' : `${report.score_improvement > 0 ? '+' : ''}${report.score_improvement}`}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Junk flagged and excluded: {report?.junk_flagged_and_excluded ?? '—'}
          </p>
        </div>
      </div>

      <div className="glass-panel p-6 rounded-2xl">
        <h3 className="text-sm font-semibold text-white mb-4">Checks (% of records passing)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-400 border-b border-slate-800">
                <th className="text-left py-2">Check</th>
                <th className="text-right py-2">Before</th>
                <th className="text-right py-2">After</th>
                <th className="py-2 w-1/3"></th>
              </tr>
            </thead>
            <tbody>
              {CHECKS.map(([key, label]) => {
                const b = before?.metrics?.[key];
                const a = after?.metrics?.[key];
                return (
                  <tr key={key} className="border-b border-slate-900">
                    <td className="py-2 text-slate-300">{label}</td>
                    <td className="py-2 text-right font-mono text-rose-300">{fmt(b)}</td>
                    <td className="py-2 text-right font-mono text-emerald-300">{fmt(a)}</td>
                    <td className="py-2 pl-4">
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500/70" style={{ width: `${a ?? 0}%` }} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-slate-500 mt-3">{report?.score_definition}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <IssueList title="Top 5 issues before cleaning" side={before} />
        <IssueList title="Top 5 issues after cleaning" side={after} />
      </div>
    </div>
  );
}
