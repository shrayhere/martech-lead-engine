import React, { useState, useEffect } from 'react';
import {
  Flame, Zap, Snowflake, Filter, Search, Download, ArrowUpDown,
  ChevronDown, ChevronRight, UserCheck, ShieldCheck, Sparkles,
  Info, Loader2, RefreshCw, Layers, CheckCircle2
} from 'lucide-react';

export default function LeadListsPage({
  initialBand = 'all',
  selectedRunId,
  runs = [],
  onSelectRun
}) {
  const [band, setBand] = useState(initialBand);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIndustry, setSelectedIndustry] = useState('ALL');
  const [selectedState, setSelectedState] = useState('ALL');
  const [selectedRep, setSelectedRep] = useState('ALL');
  const [sortBy, setSortBy] = useState('score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const limit = 25;

  const [leads, setLeads] = useState([]);
  const [totalLeads, setTotalLeads] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [bandSummary, setBandSummary] = useState({ hot: { count: 0 }, warm: { count: 0 }, cold: { count: 0 }, total: 0 });
  const [loading, setLoading] = useState(false);
  const [expandedLeadId, setExpandedLeadId] = useState(null);

  // Available filter options extracted from dataset or defaults
  const [industries, setIndustries] = useState([
    'SaaS', 'Software', 'Enterprise Technology', 'Fintech', 'Healthcare IT', 'Cybersecurity', 'Cloud Computing'
  ]);
  const [states, setStates] = useState(['CA', 'NY', 'TX', 'FL', 'IL', 'WA', 'MA', 'GA', 'NC', 'MI', 'OH']);
  const [reps, setReps] = useState(['Sarah Jenkins', 'Michael Chen', 'David Rodriguez', 'Emily Watson', 'James Wilson']);

  // Fetch band counts summary
  const fetchSummary = async () => {
    try {
      const url = selectedRunId ? `/api/leads/band-summary?run_id=${selectedRunId}` : '/api/leads/band-summary';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setBandSummary(data);
      }
    } catch (err) {
      console.error('Failed to fetch band summary:', err);
    }
  };

  // Fetch leads with query parameters
  const fetchLeads = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        band,
        page: page.toString(),
        limit: limit.toString(),
        sort_by: sortBy,
        order: sortOrder
      });

      if (selectedRunId) params.append('run_id', selectedRunId);
      if (searchQuery.trim()) params.append('q', searchQuery.trim());
      if (selectedIndustry !== 'ALL') params.append('industry', selectedIndustry);
      if (selectedState !== 'ALL') params.append('state', selectedState);
      if (selectedRep !== 'ALL') params.append('assigned_rep', selectedRep);

      const res = await fetch(`/api/leads/by-band?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setLeads(data.leads || []);
        setTotalLeads(data.total || 0);
        setTotalPages(data.total_pages || 1);
      }
    } catch (err) {
      console.error('Failed to fetch leads:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [selectedRunId]);

  useEffect(() => {
    fetchLeads();
  }, [band, searchQuery, selectedIndustry, selectedState, selectedRep, sortBy, sortOrder, page, selectedRunId]);

  const handleExportCSV = () => {
    const params = new URLSearchParams({ band });
    if (selectedRunId) params.append('run_id', selectedRunId);
    if (selectedIndustry !== 'ALL') params.append('industry', selectedIndustry);
    if (selectedState !== 'ALL') params.append('state', selectedState);
    if (selectedRep !== 'ALL') params.append('assigned_rep', selectedRep);
    window.location.href = `/api/leads/export?${params.toString()}`;
  };

  const toggleRowExpansion = (leadId) => {
    setExpandedLeadId(expandedLeadId === leadId ? null : leadId);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Header & Run Selector */}
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            Qualified Lead Lists (Hot / Warm / Cold)
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Segmented by rule-based weights & machine learning scoring with explainable rationale and 4-tier rep routing.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {runs && runs.length > 0 && (
            <div className="flex items-center gap-2 bg-slate-900/80 px-3 py-1.5 rounded-xl border border-slate-800 text-xs">
              <span className="text-slate-400 font-medium">Pipeline Run:</span>
              <select
                value={selectedRunId || ''}
                onChange={(e) => onSelectRun && onSelectRun(e.target.value)}
                className="bg-transparent text-indigo-300 font-mono text-xs focus:outline-none cursor-pointer"
              >
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id} className="bg-slate-950 text-white">
                    {r.filename} ({r.created_at ? r.created_at.slice(0, 16) : r.run_id.slice(0, 8)})
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={handleExportCSV}
            className="flex items-center space-x-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-md transition-all cursor-pointer"
          >
            <Download className="w-4 h-4" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Segmented Band Toggle Pills */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { id: 'all', label: 'All Leads', icon: Layers, count: bandSummary.total, color: 'indigo' },
          { id: 'hot', label: 'Hot Leads', icon: Flame, count: bandSummary.hot?.count, pct: bandSummary.hot?.percentage, color: 'rose' },
          { id: 'warm', label: 'Warm Leads', icon: Zap, count: bandSummary.warm?.count, pct: bandSummary.warm?.percentage, color: 'amber' },
          { id: 'cold', label: 'Cold Leads', icon: Snowflake, count: bandSummary.cold?.count, pct: bandSummary.cold?.percentage, color: 'cyan' },
        ].map((tab) => {
          const Icon = tab.icon;
          const isSelected = band === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => { setBand(tab.id); setPage(1); }}
              className={`p-4 rounded-xl border transition-all text-left flex items-center justify-between cursor-pointer ${
                isSelected
                  ? tab.color === 'rose'
                    ? 'bg-rose-500/15 border-rose-500 text-white shadow-lg shadow-rose-500/10'
                    : tab.color === 'amber'
                    ? 'bg-amber-500/15 border-amber-500 text-white shadow-lg shadow-amber-500/10'
                    : tab.color === 'cyan'
                    ? 'bg-cyan-500/15 border-cyan-500 text-white shadow-lg shadow-cyan-500/10'
                    : 'bg-indigo-600/20 border-indigo-500 text-white shadow-lg shadow-indigo-500/10'
                  : 'bg-slate-900/40 border-slate-800 text-slate-400 hover:bg-slate-900/80 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${
                  tab.color === 'rose' ? 'bg-rose-500/20 text-rose-400' :
                  tab.color === 'amber' ? 'bg-amber-500/20 text-amber-400' :
                  tab.color === 'cyan' ? 'bg-cyan-500/20 text-cyan-400' :
                  'bg-indigo-500/20 text-indigo-400'
                }`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold">{tab.label}</div>
                  <div className="text-lg font-bold font-mono text-white">
                    {tab.count ?? 0}
                    {tab.pct !== undefined && (
                      <span className="text-[11px] font-normal text-slate-400 ml-1.5 font-sans">
                        ({tab.pct}%)
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Search & Filter Toolbar */}
      <div className="glass-panel p-4 rounded-xl border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Search */}
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search leads by name, email, company, job title..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        {/* Filter Dropdowns */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Industry filter */}
          <select
            value={selectedIndustry}
            onChange={(e) => { setSelectedIndustry(e.target.value); setPage(1); }}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Industries</option>
            {industries.map((ind) => (
              <option key={ind} value={ind}>{ind}</option>
            ))}
          </select>

          {/* State filter */}
          <select
            value={selectedState}
            onChange={(e) => { setSelectedState(e.target.value); setPage(1); }}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All States</option>
            {states.map((st) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>

          {/* Rep filter */}
          <select
            value={selectedRep}
            onChange={(e) => { setSelectedRep(e.target.value); setPage(1); }}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Reps</option>
            {reps.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>

          {/* Sort By */}
          <div className="flex items-center gap-1 bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1">
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={`${sortBy}-${sortOrder}`}
              onChange={(e) => {
                const [sb, so] = e.target.value.split('-');
                setSortBy(sb);
                setSortOrder(so);
                setPage(1);
              }}
              className="bg-transparent text-slate-300 focus:outline-none cursor-pointer"
            >
              <option value="score-desc" className="bg-slate-950">Highest Score</option>
              <option value="score-asc" className="bg-slate-950">Lowest Score</option>
              <option value="company-asc" className="bg-slate-950">Company (A-Z)</option>
              <option value="date-desc" className="bg-slate-950">Most Recent Activity</option>
            </select>
          </div>
        </div>
      </div>

      {/* Leads Table */}
      <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden">
        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center space-y-3 text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
            <p className="text-xs">Loading leads...</p>
          </div>
        ) : leads.length === 0 ? (
          <div className="p-16 text-center text-slate-500 space-y-2">
            <Layers className="w-10 h-10 mx-auto text-slate-600 mb-2" />
            <p className="text-sm font-semibold text-slate-400">No leads matched your criteria</p>
            <p className="text-xs">Try selecting a different score band or resetting the active filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="p-3 w-10"></th>
                  <th className="p-3">Score & Band</th>
                  <th className="p-3">Lead Contact</th>
                  <th className="p-3">Company & Role</th>
                  <th className="p-3">Location & Phone</th>
                  <th className="p-3">Industry & Size</th>
                  <th className="p-3">Assigned Rep</th>
                  <th className="p-3 text-right">Why This Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                {leads.map((lead) => {
                  const isExpanded = expandedLeadId === lead.id;
                  const bandBadge =
                    lead.band === 'Hot'
                      ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                      : lead.band === 'Warm'
                      ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                      : 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30';

                  return (
                    <React.Fragment key={lead.id}>
                      <tr
                        onClick={() => toggleRowExpansion(lead.id)}
                        className={`hover:bg-slate-800/40 transition-colors cursor-pointer ${
                          isExpanded ? 'bg-indigo-950/20' : ''
                        }`}
                      >
                        <td className="p-3 text-slate-500">
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-indigo-400" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-slate-500" />
                          )}
                        </td>

                        {/* Score & Band */}
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-base font-extrabold text-white">
                              {lead.score}
                            </span>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${bandBadge}`}>
                              {lead.band}
                            </span>
                          </div>
                          {lead.ml_score !== null && (
                            <span className="text-[10px] text-slate-500 font-mono block">
                              ML: {lead.ml_score} • Rule: {lead.rule_score}
                            </span>
                          )}
                        </td>

                        {/* Lead Name & Email */}
                        <td className="p-3">
                          <div className="font-semibold text-slate-100">{lead.name}</div>
                          <div className="text-slate-400 text-[11px]">{lead.email || <span className="text-rose-400 italic">No email</span>}</div>
                        </td>

                        {/* Company & Role */}
                        <td className="p-3">
                          <div className="font-medium text-slate-200">{lead.company || '-'}</div>
                          <div className="text-slate-400 text-[11px]">{lead.job_title || '-'}</div>
                        </td>

                        {/* Location & Phone */}
                        <td className="p-3 font-mono text-[11px]">
                          <div className="text-slate-300">{lead.phone || '-'}</div>
                          <div className="text-slate-400 font-sans">{lead.state || '-'}</div>
                        </td>

                        {/* Industry & Size */}
                        <td className="p-3">
                          <div className="text-slate-300">{lead.industry || 'General Business'}</div>
                          <div className="text-slate-500 text-[10px]">{lead.company_size || 50} employees</div>
                        </td>

                        {/* Assigned Rep */}
                        <td className="p-3">
                          <div className="font-medium text-indigo-300">{lead.assigned_rep?.name || 'Unassigned'}</div>
                          <div className="text-slate-500 text-[10px] truncate max-w-[160px]" title={lead.assignment_reason}>
                            {lead.assignment_reason}
                          </div>
                        </td>

                        {/* Why this score trigger */}
                        <td className="p-3 text-right">
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleRowExpansion(lead.id); }}
                            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded-lg text-[11px] font-semibold transition-all inline-flex items-center gap-1"
                          >
                            <Info className="w-3.5 h-3.5" />
                            <span>Why Score</span>
                          </button>
                        </td>
                      </tr>

                      {/* Expandable "Why this score" Drawer Row */}
                      {isExpanded && (
                        <tr className="bg-slate-900/70 border-b border-slate-800">
                          <td colSpan={8} className="p-5">
                            <div className="space-y-4">
                              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                                <div>
                                  <h4 className="font-bold text-white text-sm flex items-center gap-2">
                                    <Sparkles className="w-4 h-4 text-indigo-400" />
                                    Scoring & Assignment Diagnostic for {lead.name}
                                  </h4>
                                  <p className="text-[11px] text-slate-400">
                                    Lead ID: #{lead.id} • Active Score: <b className="text-white">{lead.score}/100</b> ({lead.band} Band)
                                  </p>
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                  {lead.cleaning_flags?.map((flag, idx) => (
                                    <span key={idx} className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-[10px] font-semibold">
                                      {flag}
                                    </span>
                                  ))}
                                </div>
                              </div>

                              {/* Top 3 Scoring Reasons */}
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                {lead.top_3_reasons?.map((reason, idx) => (
                                  <div key={idx} className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                                    <div className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider mb-1">
                                      Key Signal #{idx + 1}
                                    </div>
                                    <div className="text-xs text-slate-200">{reason}</div>
                                  </div>
                                ))}
                              </div>

                              {/* Rep Routing Explanation */}
                              <div className="p-3 bg-slate-950/60 rounded-xl border border-indigo-500/20 flex items-start gap-3 text-xs">
                                <UserCheck className="w-4 h-4 text-indigo-400 mt-0.5 shrink-0" />
                                <div>
                                  <span className="font-semibold text-indigo-300">Routing Rule Matched: </span>
                                  <span className="text-slate-300">{lead.assignment_reason}</span>
                                </div>
                              </div>

                              {/* Extra Unmapped Fields from CSV */}
                              {lead.extra_fields && Object.keys(lead.extra_fields).length > 0 && (
                                <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800/80 text-xs">
                                  <div className="font-semibold text-slate-400 mb-1.5">Preserved Extra CSV Fields:</div>
                                  <div className="flex flex-wrap gap-2">
                                    {Object.entries(lead.extra_fields).map(([k, v]) => (
                                      <span key={k} className="px-2 py-0.5 bg-slate-900 text-slate-300 rounded font-mono text-[10px] border border-slate-800">
                                        {k}: <b>{String(v)}</b>
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="p-4 bg-slate-900/60 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <div>
              Showing page <b className="text-white">{page}</b> of <b className="text-white">{totalPages}</b> ({totalLeads} total leads)
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-lg transition-all cursor-pointer"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 rounded-lg transition-all cursor-pointer"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
