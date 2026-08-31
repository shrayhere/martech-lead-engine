import React, { useState, useEffect } from 'react';
import { Cpu, Flame, Thermometer, Snowflake, ToggleLeft, ToggleRight, Sparkles, Filter, X, ChevronRight, Info, Play, Loader2, ArrowRight } from 'lucide-react';

export default function ScoringPage({ onProceedToAssignment }) {
  const [scoringMode, setScoringMode] = useState('rule'); // 'rule' or 'ml'
  const [leads, setLeads] = useState([]);
  const [distribution, setDistribution] = useState({ Hot: 0, Warm: 0, Cold: 0 });
  const [selectedBand, setSelectedBand] = useState('ALL');
  const [selectedIndustry, setSelectedIndustry] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLead, setSelectedLead] = useState(null); // For signal breakdown drawer
  const [isScoring, setIsScoring] = useState(false);
  const [config, setConfig] = useState(null);

  const fetchScoreConfig = async () => {
    try {
      const res = await fetch('/api/leads/score-config');
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
      }
    } catch (err) {
      console.error('Failed to fetch score config:', err);
    }
  };

  const fetchScoredLeads = async (mode = scoringMode) => {
    try {
      const res = await fetch(`/api/leads/scored?scoring_mode=${mode}`);
      if (res.ok) {
        const data = await res.json();
        setLeads(data.leads || []);
        
        // Compute distribution stats
        let h = 0, w = 0, c = 0;
        (data.leads || []).forEach((l) => {
          const score = mode === 'rule' ? (l.rule_score ?? 0) : (l.ml_score ?? 0);
          if (score >= 80) h++;
          else if (score >= 50) w++;
          else c++;
        });
        setDistribution({ Hot: h, Warm: w, Cold: c });
      }
    } catch (err) {
      console.error('Failed to fetch scored leads:', err);
    }
  };

  const runScoring = async (modeToRun = scoringMode) => {
    setIsScoring(true);
    try {
      const res = await fetch(`/api/leads/score?mode=${modeToRun}`, { method: 'POST' });
      if (res.ok) {
        await fetchScoredLeads(modeToRun);
      }
    } catch (err) {
      console.error('Scoring calculation failed:', err);
    } finally {
      setIsScoring(false);
    }
  };

  useEffect(() => {
    fetchScoreConfig();
    fetchScoredLeads(scoringMode);
  }, [scoringMode]);

  const handleToggleMode = async (newMode) => {
    setScoringMode(newMode);
    await runScoring(newMode);
  };

  // Filter leads
  const filteredLeads = leads.filter((lead) => {
    const activeScore = scoringMode === 'rule' ? (lead.rule_score ?? 0) : (lead.ml_score ?? 0);
    const band = activeScore >= 80 ? 'Hot' : activeScore >= 50 ? 'Warm' : 'Cold';

    if (selectedBand !== 'ALL' && band !== selectedBand) return false;
    if (selectedIndustry !== 'ALL' && lead.industry !== selectedIndustry) return false;
    
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const name = `${lead.first_name || ''} ${lead.last_name || ''}`.toLowerCase();
      const comp = (lead.company || '').toLowerCase();
      const title = (lead.job_title || '').toLowerCase();
      return name.includes(q) || comp.includes(q) || title.includes(q);
    }
    return true;
  });

  const getBandBadge = (score) => {
    if (score >= 80) {
      return (
        <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1.5 w-fit">
          <Flame className="w-3.5 h-3.5 text-rose-400" />
          Hot ({score.toFixed(1)})
        </span>
      );
    } else if (score >= 50) {
      return (
        <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 w-fit">
          <Thermometer className="w-3.5 h-3.5 text-amber-400" />
          Warm ({score.toFixed(1)})
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1.5 w-fit">
        <Snowflake className="w-3.5 h-3.5 text-sky-400" />
        Cold ({score.toFixed(1)})
      </span>
    );
  };

  const industriesList = Array.from(new Set(leads.map((l) => l.industry).filter(Boolean)));

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Top Banner & Mode Toggle */}
      <div className="glass-panel p-6 rounded-2xl flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Cpu className="w-5 h-5 text-indigo-400" />
            Stage 3: Lead Scoring Engine
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Scores leads from 0 to 100 combining firmographic signals (company size, industry, title) and behavioral recency.
          </p>
        </div>

        {/* Rule vs ML Toggle */}
        <div className="flex flex-col sm:flex-row items-center gap-4 bg-slate-900/80 p-2 rounded-2xl border border-slate-800 shrink-0">
          <span className="text-xs font-semibold text-slate-400 px-2">Scoring Engine Mode:</span>
          <div className="flex items-center space-x-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => handleToggleMode('rule')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                scoringMode === 'rule'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Rule-Based (Explainable)
            </button>
            <button
              onClick={() => handleToggleMode('ml')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                scoringMode === 'ml'
                  ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Scikit-Learn ML Model
            </button>
          </div>

          <button
            onClick={() => runScoring(scoringMode)}
            disabled={isScoring}
            className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded-xl text-xs font-semibold border border-indigo-500/30 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {isScoring ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-indigo-300" />}
            <span>Recalculate</span>
          </button>
        </div>
      </div>

      {/* Distribution Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-slate-500">
          <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Total Scored Leads</span>
          <p className="text-3xl font-extrabold text-white mt-2">{leads.length}</p>
          <p className="text-[11px] text-slate-400 mt-1">Active Model: {scoringMode === 'rule' ? 'Weighted Rule' : 'ML Classifier'}</p>
        </div>

        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-rose-500 bg-rose-950/10">
          <div className="flex items-center justify-between">
            <span className="text-xs text-rose-400 font-semibold uppercase tracking-wider">Hot Leads (80-100)</span>
            <Flame className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-3xl font-extrabold text-rose-400 mt-2">{distribution.Hot}</p>
          <p className="text-[11px] text-slate-400 mt-1">High conversion priority • Immediate sales route</p>
        </div>

        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-amber-500 bg-amber-950/10">
          <div className="flex items-center justify-between">
            <span className="text-xs text-amber-400 font-semibold uppercase tracking-wider">Warm Leads (50-79)</span>
            <Thermometer className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-3xl font-extrabold text-amber-400 mt-2">{distribution.Warm}</p>
          <p className="text-[11px] text-slate-400 mt-1">Nurture sequence • Sales outreach</p>
        </div>

        <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-slate-700">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Cold Leads (0-49)</span>
            <Snowflake className="w-4 h-4 text-sky-400" />
          </div>
          <p className="text-3xl font-extrabold text-slate-300 mt-2">{distribution.Cold}</p>
          <p className="text-[11px] text-slate-400 mt-1">Low engagement / non-target industry</p>
        </div>
      </div>

      {/* Filters & Scored Leads Table */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          {/* Search Input */}
          <div className="relative w-full md:w-72">
            <input
              type="text"
              placeholder="Search lead name, company, title..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Band Filter */}
            <div className="flex items-center space-x-1 bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs">
              <span className="text-slate-400 px-2 font-medium">Band:</span>
              {['ALL', 'Hot', 'Warm', 'Cold'].map((b) => (
                <button
                  key={b}
                  onClick={() => setSelectedBand(b)}
                  className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                    selectedBand === b ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {b}
                </button>
              ))}
            </div>

            {/* Industry Filter */}
            <select
              value={selectedIndustry}
              onChange={(e) => setSelectedIndustry(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Industries</option>
              {industriesList.map((ind) => (
                <option key={ind} value={ind}>{ind}</option>
              ))}
            </select>

            {onProceedToAssignment && (
              <button
                onClick={onProceedToAssignment}
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-500/20 transition-all cursor-pointer"
              >
                <span>Proceed to Rep Assignment</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Leads Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-3">Score & Band</th>
                <th className="p-3">Lead Name</th>
                <th className="p-3">Job Title</th>
                <th className="p-3">Company</th>
                <th className="p-3">Industry</th>
                <th className="p-3">Engagement</th>
                <th className="p-3">State</th>
                <th className="p-3 text-right">Explainability</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
              {filteredLeads.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    No scored leads found matching your criteria.
                  </td>
                </tr>
              ) : (
                filteredLeads.map((lead) => {
                  const score = scoringMode === 'rule' ? (lead.rule_score ?? 0) : (lead.ml_score ?? 0);
                  return (
                    <tr
                      key={lead.id}
                      onClick={() => setSelectedLead(lead)}
                      className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                    >
                      <td className="p-3">{getBandBadge(score)}</td>
                      <td className="p-3 font-semibold text-white">{lead.first_name} {lead.last_name}</td>
                      <td className="p-3 text-slate-300">{lead.job_title || '-'}</td>
                      <td className="p-3 font-medium text-indigo-300">{lead.company}</td>
                      <td className="p-3 text-slate-400">{lead.industry}</td>
                      <td className="p-3 font-mono text-cyan-300 font-semibold">{lead.engagement_score ?? 0} / 100</td>
                      <td className="p-3 font-mono text-slate-400">{lead.state}</td>
                      <td className="p-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedLead(lead);
                          }}
                          className="px-3 py-1 bg-slate-800 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg text-[11px] font-semibold transition-all border border-indigo-500/20"
                        >
                          View Breakdown →
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Signal Explainability Drawer / Modal */}
      {selectedLead && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex justify-end animate-in fade-in duration-200">
          <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full p-6 overflow-y-auto space-y-6 shadow-2xl">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-xs text-indigo-400 font-semibold uppercase tracking-wider">Lead Explainability Audit</span>
                <h3 className="text-xl font-bold text-white mt-1">
                  {selectedLead.first_name} {selectedLead.last_name}
                </h3>
                <p className="text-xs text-slate-400">{selectedLead.job_title} at {selectedLead.company}</p>
              </div>
              <button
                onClick={() => setSelectedLead(null)}
                className="p-2 bg-slate-800 hover:bg-slate-700 rounded-xl text-slate-400 hover:text-white cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Score Highlight Box */}
            <div className="p-5 bg-gradient-to-r from-indigo-950/60 to-slate-900 border border-indigo-500/30 rounded-2xl flex items-center justify-between">
              <div>
                <span className="text-xs text-slate-400">Calculated Score ({scoringMode === 'rule' ? 'Rule-Based Model' : 'ML Classifier'})</span>
                <div className="text-3xl font-extrabold text-white mt-1">
                  {scoringMode === 'rule' ? selectedLead.rule_score : selectedLead.ml_score} / 100
                </div>
              </div>
              {getBandBadge(scoringMode === 'rule' ? selectedLead.rule_score : selectedLead.ml_score)}
            </div>

            {/* Breakdown Signals List */}
            {selectedLead.score_breakdown ? (
              (() => {
                const breakdown = JSON.parse(selectedLead.score_breakdown);
                return (
                  <div className="space-y-4">
                    <div className="flex justify-between text-xs text-slate-400 font-semibold uppercase border-b border-slate-800 pb-2">
                      <span>Signal Parameter</span>
                      <span>Contribution</span>
                    </div>

                    <div className="space-y-3">
                      {breakdown.signals.map((sig, idx) => (
                        <div key={idx} className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md ${
                                sig.category === 'Firmographic' ? 'bg-indigo-500/20 text-indigo-300' : 'bg-cyan-500/20 text-cyan-300'
                              }`}>
                                {sig.category}
                              </span>
                              <span className="text-sm font-bold text-white">{sig.name}</span>
                            </div>
                            <span className="text-sm font-mono font-bold text-emerald-400">
                              +{sig.points_contributed} pts
                            </span>
                          </div>

                          <div className="text-xs text-slate-400">
                            Raw Value: <span className="text-slate-200 font-medium">{sig.raw_value}</span>
                          </div>
                          <p className="text-[11px] text-slate-500 italic">{sig.explanation}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()
            ) : (
              <p className="text-sm text-slate-400">No signal breakdown available for this record.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
