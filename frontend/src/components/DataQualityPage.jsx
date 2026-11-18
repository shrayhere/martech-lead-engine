import React, { useState, useEffect } from 'react';
import { ShieldCheck, Play, Layers, AlertOctagon, CheckCircle, BarChart3, Info, ArrowRight, Loader2, Sparkles, Filter } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export default function DataQualityPage({ onProceedToScoring }) {
  const [report, setReport] = useState(null);
  const [mergedLogs, setMergedLogs] = useState([]);
  const [cleanLeads, setCleanLeads] = useState([]);
  const [isCleaning, setIsCleaning] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('merged'); // 'merged' or 'clean' or 'junk'

  const fetchCleanData = async () => {
    try {
      const resLogs = await fetch('/api/leads/merged-log');
      if (resLogs.ok) {
        const dataLogs = await resLogs.json();
        setMergedLogs(dataLogs.merged_logs || []);
      }

      const resClean = await fetch('/api/leads/clean');
      if (resClean.ok) {
        const dataClean = await resClean.json();
        setCleanLeads(dataClean.leads || []);
      }
    } catch (err) {
      console.error('Failed to fetch clean data:', err);
    }
  };

  const runCleaning = async () => {
    setIsCleaning(true);
    setError(null);
    try {
      const res = await fetch('/api/leads/clean', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Data cleaning failed');
      }
      setReport(data);
      await fetchCleanData();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsCleaning(false);
    }
  };

  useEffect(() => {
    fetchCleanData();
  }, []);

  // Prepare Recharts Before vs After dataset
  const chartData = report ? [
    {
      metric: 'Duplicate Rate (%)',
      Before: report.duplicate_rate_before,
      After: report.duplicate_rate_after,
    },
    {
      metric: 'Data Completeness (%)',
      Before: report.completeness_score_before,
      After: report.completeness_score_after,
    }
  ] : null; // no numbers are shown until a cleaning run has produced real ones

  const junkLeads = cleanLeads.filter(l => l.is_junk);
  const validCleanLeads = cleanLeads.filter(l => !l.is_junk);

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Top Action Bar */}
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            Stage 2: Data Quality & RapidFuzz Deduplication
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Normalize states, E.164 phone numbers, filter junk placeholders, and merge fuzzy duplicates.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={runCleaning}
            disabled={isCleaning}
            className="flex items-center space-x-2 px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white rounded-xl text-sm font-semibold shadow-lg shadow-indigo-500/20 transition-all cursor-pointer disabled:opacity-50"
          >
            {isCleaning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Running RapidFuzz Pipeline...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Execute Cleaning & Deduplication</span>
              </>
            )}
          </button>

          {cleanLeads.length > 0 && onProceedToScoring && (
            <button
              onClick={onProceedToScoring}
              className="flex items-center space-x-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-sm font-bold shadow-lg shadow-emerald-500/20 transition-all cursor-pointer"
            >
              <span>Proceed to Lead Scoring</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm flex items-center gap-3">
          <AlertOctagon className="w-5 h-5 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="glass-panel p-5 rounded-2xl space-y-2 border-l-4 border-l-indigo-500">
          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Duplicate Rate</span>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-white">
              {report ? `${report.duplicate_rate_after}%` : '—'}
            </span>
            <span className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
              Before: {report ? `${report.duplicate_rate_before}%` : '—'}
            </span>
          </div>
          <p className="text-[11px] text-slate-400">
            {report
              ? 'Exact email/phone matches, plus guarded fuzzy matches (same last name, similar first name, same company or domain).'
              : 'Run cleaning to measure the duplicate rate.'}
          </p>
        </div>

        <div className="glass-panel p-5 rounded-2xl space-y-2 border-l-4 border-l-emerald-500">
          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Completeness Score</span>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-emerald-400">
              {report ? `${report.completeness_score_after}%` : '—'}
            </span>
            <span className="text-xs font-semibold text-slate-300 bg-slate-800 px-2 py-0.5 rounded-full">
              Before: {report ? `${report.completeness_score_before}%` : '—'}
            </span>
          </div>
          <p className="text-[11px] text-slate-400">
            {report
              ? 'Average share of populated fields after state & phone E.164 normalization.'
              : 'Run cleaning to measure completeness.'}
          </p>
        </div>

        <div className="glass-panel p-5 rounded-2xl space-y-2 border-l-4 border-l-amber-500">
          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Junk Rows Filtered</span>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-amber-400">
              {report ? report.junk_rows_removed : junkLeads.length}
            </span>
            <span className="text-xs font-semibold text-amber-300 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
              Junk Flagged
            </span>
          </div>
          <p className="text-[11px] text-slate-400">
            Rows missing both email/phone or containing 'test', 'n/a', 'asdf' placeholders.
          </p>
        </div>

        <div className="glass-panel p-5 rounded-2xl space-y-2 border-l-4 border-l-cyan-500">
          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Clean Leads Stored</span>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-cyan-300">
              {report ? report.total_clean_stored : validCleanLeads.length}
            </span>
            <span className="text-xs font-semibold text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
              Raw: {report ? report.total_raw_processed : cleanLeads.length}
            </span>
          </div>
          <p className="text-[11px] text-slate-400">
            Cleaned, deduplicated master records saved in `clean_leads` table.
          </p>
        </div>
      </div>

      {/* Chart & RapidFuzz Threshold Explanation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recharts Bar Chart */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-indigo-400" />
              Before vs After Quality Metrics Comparison
            </h3>
            <span className="text-xs text-slate-400 font-mono">Recharts Analytics</span>
          </div>

          <div className="h-64 w-full pt-2">
            {!chartData ? (
              <div className="h-full flex items-center justify-center text-sm text-slate-500 border border-dashed border-slate-700 rounded-xl">
                No data yet. Run cleaning to compare before and after.
              </div>
            ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="metric" stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', color: '#fff' }}
                  cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
                />
                <Legend wrapperStyle={{ color: '#cbd5e1', fontSize: '12px' }} />
                <Bar dataKey="Before" fill="#f43f5e" radius={[6, 6, 0, 0]} name="Before Cleaning" />
                <Bar dataKey="After" fill="#10b981" radius={[6, 6, 0, 0]} name="After Cleaning" />
              </BarChart>
            </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* RapidFuzz Threshold Rationale Box */}
        <div className="glass-panel p-6 rounded-2xl space-y-4 border border-indigo-500/20 bg-indigo-950/20">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Info className="w-4 h-4 text-indigo-400" />
            How Duplicates Are Matched
          </h3>

          <div className="p-3 bg-indigo-500/10 border border-indigo-500/30 rounded-xl">
            <span className="text-xs font-bold text-indigo-300">Composite similarity threshold: 85%, with name guards</span>
          </div>

          <div className="text-xs text-slate-300 space-y-2 leading-relaxed">
            <p>
              Records with the same email or phone merge directly. A fuzzy match (typos with no shared identifier) must pass all of:
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-400">
              <li>Same last name.</li>
              <li>First name at least 85% similar (<em>Jonathan</em> / <em>Jonathon</em>).</li>
              <li>Same company or email domain.</li>
              <li>RapidFuzz <code className="bg-slate-900 px-1 py-0.5 rounded text-indigo-300 font-mono text-[10px]">token_sort_ratio</code> of name | company | email of at least 85%.</li>
            </ul>
            <p>
              <strong className="text-indigo-400">Why the guards:</strong> the composite score alone merged different colleagues at the same company. On the sample data (20 planted duplicates) the guarded rule made 20 correct merges and 0 wrong ones; see <code className="bg-slate-900 px-1 py-0.5 rounded text-indigo-300 font-mono text-[10px]">docs/dedup_evaluation.md</code>.
            </p>
          </div>
        </div>
      </div>

      {/* Tabs for Merged Audit Log / Clean Leads / Junk Leads */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-slate-800 pb-4 gap-4">
          <div className="flex space-x-2">
            <button
              onClick={() => setActiveTab('merged')}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'merged'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              Merged Duplicates Log ({mergedLogs.length})
            </button>
            <button
              onClick={() => setActiveTab('clean')}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'clean'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              Cleaned Master Records ({validCleanLeads.length})
            </button>
            <button
              onClick={() => setActiveTab('junk')}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'junk'
                  ? 'bg-amber-600 text-white shadow-md'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              Junk Flagged ({junkLeads.length})
            </button>
          </div>

          <span className="text-xs text-slate-400 font-mono">
            Table: {activeTab === 'merged' ? '`merged_leads_log`' : '`clean_leads`'}
          </span>
        </div>

        {/* Tab 1: Merged Duplicates Audit Log */}
        {activeTab === 'merged' && (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            {mergedLogs.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">
                No duplicate merges logged yet. Click <strong>"Execute Cleaning & Deduplication"</strong> above.
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="p-3">Kept Record</th>
                    <th className="p-3">Archived Record</th>
                    <th className="p-3">Archived Lead Name</th>
                    <th className="p-3">Archived Company</th>
                    <th className="p-3">Archived Email</th>
                    <th className="p-3">Similarity Score</th>
                    <th className="p-3">Audit Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                  {mergedLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="p-3 font-mono font-bold text-indigo-400" title={log.id_type === 'csv_row' ? 'Row number in the uploaded CSV' : 'raw_leads.id'}>
                        {log.id_type === 'csv_row' ? 'Row' : 'Raw'} #{log.winner_raw_lead_id ?? log.winner_lead_id}
                      </td>
                      <td className="p-3 font-mono text-slate-300" title={log.id_type === 'csv_row' ? 'Row number in the uploaded CSV' : 'raw_leads.id'}>
                        {log.id_type === 'csv_row' ? 'Row' : 'Raw'} #{log.archived_raw_lead_id}
                      </td>
                      <td className="p-3 font-medium text-slate-200">{log.archived_lead_name || '-'}</td>
                      <td className="p-3 text-slate-300">{log.archived_company || '-'}</td>
                      <td className="p-3 text-slate-400 font-mono">{log.archived_email || '-'}</td>
                      <td className="p-3">
                        <span className="px-2.5 py-1 bg-indigo-500/20 text-indigo-300 font-mono font-bold rounded-lg border border-indigo-500/30">
                          {log.similarity_score}%
                        </span>
                      </td>
                      <td className="p-3 text-slate-400 max-w-xs truncate">{log.merge_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Tab 2: Clean Master Records */}
        {activeTab === 'clean' && (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            {validCleanLeads.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">No clean leads stored yet.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="p-3">ID</th>
                    <th className="p-3">Name</th>
                    <th className="p-3">Email</th>
                    <th className="p-3">Normalized Company</th>
                    <th className="p-3">Standard State</th>
                    <th className="p-3">E.164 Phone</th>
                    <th className="p-3">Industry</th>
                    <th className="p-3">Cluster ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                  {validCleanLeads.slice(0, 20).map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="p-3 font-mono text-slate-500">{lead.id}</td>
                      <td className="p-3 font-semibold text-white">{lead.first_name} {lead.last_name}</td>
                      <td className="p-3 text-indigo-300">{lead.email}</td>
                      <td className="p-3 font-medium text-slate-200">{lead.company}</td>
                      <td className="p-3 font-mono text-emerald-400 font-bold">{lead.state}</td>
                      <td className="p-3 font-mono text-cyan-300">{lead.phone || '-'}</td>
                      <td className="p-3 text-slate-400">{lead.industry}</td>
                      <td className="p-3 font-mono text-xs text-slate-500">{lead.duplicate_cluster_id || 'Singleton'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Tab 3: Junk Leads */}
        {activeTab === 'junk' && (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            {junkLeads.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">No junk rows detected.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="p-3">ID</th>
                    <th className="p-3">Name</th>
                    <th className="p-3">Email</th>
                    <th className="p-3">Company</th>
                    <th className="p-3">Flag Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                  {junkLeads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="p-3 font-mono text-slate-500">{lead.id}</td>
                      <td className="p-3 font-medium text-slate-300">{lead.first_name || '-'} {lead.last_name || '-'}</td>
                      <td className="p-3 text-rose-400">{lead.email || 'None'}</td>
                      <td className="p-3 text-slate-400">{lead.company || 'None'}</td>
                      <td className="p-3 text-amber-400 font-medium">{lead.junk_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
