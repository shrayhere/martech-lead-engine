import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Flame, 
  ShieldCheck, 
  Copy, 
  Clock, 
  Play, 
  ArrowRight, 
  Sparkles, 
  CheckCircle2, 
  TrendingUp, 
  UploadCloud, 
  ChevronRight,
  Filter,
  BarChart3,
  Loader2
} from 'lucide-react';

export default function DashboardHome({
  runs = [],
  cleanLeads = [],
  onRunDemo,
  onNavigate,
  isProcessingDemo = false
}) {
  const latestRun = runs.length > 0 ? runs[0] : null;
  const totalLeads = cleanLeads.length || (latestRun?.row_count_out || 0);
  const hotLeads = cleanLeads.filter(l => l.score_band === 'Hot').length;
  const warmLeads = cleanLeads.filter(l => l.score_band === 'Warm').length;
  const coldLeads = cleanLeads.filter(l => l.score_band === 'Cold').length;

  const duplicatesMerged = latestRun?.duplicates_merged || 0;
  const fieldsFixed = latestRun?.fields_fixed || 0;
  // Estimate ~20s saved per row manually reviewed/cleaned
  const estimatedHoursSaved = totalLeads > 0 
    ? Math.max(1, Math.round(((totalLeads + duplicatesMerged) * 20) / 3600))
    : 0;

  // Real Data Quality Report
  const [qualityReport, setQualityReport] = useState(null);

  useEffect(() => {
    let mounted = true;
    const url = latestRun?.run_id ? `/api/quality/report?run_id=${latestRun.run_id}` : '/api/quality/report';
    fetch(url)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (mounted && d) setQualityReport(d);
      })
      .catch(() => {});
    return () => { mounted = false; };
  }, [latestRun?.run_id]);

  const afterScore = qualityReport?.after?.score;
  const beforeScore = qualityReport?.before?.score;
  const dqImprovement = (afterScore !== undefined && beforeScore !== undefined) 
    ? (afterScore - beforeScore) 
    : null;

  const kpis = [
    {
      title: 'Total Active Leads',
      value: totalLeads > 0 ? totalLeads.toLocaleString() : '—',
      icon: Users,
      trend: totalLeads > 0 ? `${totalLeads.toLocaleString()} records` : null,
      desc: 'Validated B2B records',
      accent: 'from-blue-500/20 to-indigo-500/10 text-blue-400 border-blue-500/30'
    },
    {
      title: 'Hot Leads Routed',
      value: hotLeads > 0 ? hotLeads.toLocaleString() : '—',
      icon: Flame,
      trend: hotLeads > 0 && totalLeads > 0 ? `${Math.round((hotLeads / totalLeads) * 100)}% of total` : null,
      desc: 'Score ≥ 80 to sales reps',
      accent: 'from-amber-500/20 to-orange-500/10 text-amber-400 border-amber-500/30'
    },
    {
      title: 'Data Quality Health',
      value: afterScore !== undefined ? `${afterScore}%` : '—',
      icon: ShieldCheck,
      trend: dqImprovement !== null ? `${dqImprovement > 0 ? '+' : ''}${dqImprovement}% vs uploaded` : null,
      desc: 'Pass rate on 8 core checks',
      accent: 'from-emerald-500/20 to-teal-500/10 text-emerald-400 border-emerald-500/30'
    },
    {
      title: 'Duplicates Merged',
      value: duplicatesMerged > 0 ? duplicatesMerged.toLocaleString() : (latestRun ? '0' : '—'),
      icon: Copy,
      trend: duplicatesMerged > 0 ? `${duplicatesMerged} resolved` : null,
      desc: 'Smart blocking match',
      accent: 'from-purple-500/20 to-indigo-500/10 text-purple-400 border-purple-500/30'
    },
    {
      title: 'Manual Work Saved',
      value: estimatedHoursSaved > 0 ? `${estimatedHoursSaved} hrs` : '—',
      icon: Clock,
      trend: estimatedHoursSaved > 0 ? '~20s per record' : null,
      desc: 'Autonomous processing',
      accent: 'from-teal-500/20 to-emerald-500/10 text-teal-400 border-teal-500/30'
    }
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Welcome / Demo Hero Banner (Shown especially on first visit or when no leads) */}
      <div className="relative overflow-hidden rounded-2xl p-6 sm:p-8 border bg-gradient-to-br from-indigo-950/60 via-slate-900 to-slate-950 border-indigo-500/30 shadow-xl">
        <div className="absolute top-0 right-0 -mt-12 -mr-12 w-96 h-96 rounded-full bg-gradient-to-br from-indigo-600/10 to-teal-500/10 blur-3xl pointer-events-none" />
        
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="max-w-2xl space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              <Sparkles className="w-3.5 h-3.5" />
              Autonomous B2B Lead Quality &amp; Routing Engine
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Turn messy CSV lists into sales-ready, routed leads in seconds.
            </h1>
            <p className="text-sm sm:text-base text-slate-300">
              Auto-formats phone numbers, detects international titles &amp; states, purges disposable junk, merges duplicates, and routes hot leads to the right sales reps.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
            <button
              onClick={onRunDemo}
              disabled={isProcessingDemo}
              className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-indigo-600 to-teal-600 hover:from-indigo-500 hover:to-teal-500 shadow-lg shadow-indigo-500/20 transition-all cursor-pointer disabled:opacity-50"
            >
              {isProcessingDemo ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Processing Demo Data…</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>Run Demo with Sample Data</span>
                </>
              )}
            </button>
            <button
              onClick={() => onNavigate('smart')}
              className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-semibold text-sm text-slate-200 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 transition-all cursor-pointer"
            >
              <UploadCloud className="w-4 h-4" />
              <span>Upload Your File</span>
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div 
              key={kpi.title}
              className={`p-4 rounded-xl border bg-gradient-to-b ${kpi.accent} transition-transform hover:-translate-y-0.5`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">{kpi.title}</span>
                <Icon className="w-4 h-4" />
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-black text-white tracking-tight">{kpi.value}</span>
              </div>
              <div className="mt-1 flex items-center justify-between text-[11px]">
                {kpi.trend ? (
                  <span className="text-emerald-400 font-semibold">{kpi.trend}</span>
                ) : (
                  <span className="text-slate-500 font-normal">—</span>
                )}
                <span className="text-slate-400 truncate">{kpi.desc}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Breakdown Chart & Quick Pipeline Stepper Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lead Score Bands */}
        <div className="p-5 rounded-xl border bg-slate-900/60 border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-indigo-400" /> Lead Score Distribution
            </h3>
            <button 
              onClick={() => onNavigate('leads')}
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              <span>View all</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-3 pt-2">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-amber-400 flex items-center gap-1.5">
                  <Flame className="w-3.5 h-3.5" /> Hot Leads (Score 80–100)
                </span>
                <span className="text-white font-mono font-bold">{hotLeads}</span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-amber-500 to-orange-500 rounded-full" 
                  style={{ width: `${totalLeads ? (hotLeads / totalLeads) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-blue-400 flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5" /> Warm Leads (Score 50–79)
                </span>
                <span className="text-white font-mono font-bold">{warmLeads}</span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 rounded-full" 
                  style={{ width: `${totalLeads ? (warmLeads / totalLeads) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-slate-400 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" /> Cold Leads (Score 0–49)
                </span>
                <span className="text-white font-mono font-bold">{coldLeads}</span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-slate-600 rounded-full" 
                  style={{ width: `${totalLeads ? (coldLeads / totalLeads) * 100 : 0}%` }}
                />
              </div>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-300">
            <strong>Calibrated Scoring:</strong> Seniority, target industry, engagement, company size, and recency are weighted to highlight leads with highest buying intent.
          </div>
        </div>

        {/* Pipeline Execution Stages */}
        <div className="p-5 rounded-xl border bg-slate-900/60 border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" /> Pipeline Automation
            </h3>
            <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> 4 Stages Active
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/50">
              <span className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-[10px] shrink-0">1</span>
              <div>
                <p className="font-semibold text-white">Smart Parsing &amp; Mapping</p>
                <p className="text-slate-400 text-[11px]">Understands any header variations, cleans UTF-8 &amp; delimiters</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/50">
              <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-[10px] shrink-0">2</span>
              <div>
                <p className="font-semibold text-white">Quality Cleaning &amp; Deduplication</p>
                <p className="text-slate-400 text-[11px]">E.164 phone normalization, international state detection, O(n) deduplication</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/50">
              <span className="w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-[10px] shrink-0">3</span>
              <div>
                <p className="font-semibold text-white">Explainable Scoring &amp; AI Personas</p>
                <p className="text-slate-400 text-[11px]">Classifies decision makers, predicts conversion likelihood, suggests next actions</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/50">
              <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center font-bold text-[10px] shrink-0">4</span>
              <div>
                <p className="font-semibold text-white">Territory &amp; Workload Routing</p>
                <p className="text-slate-400 text-[11px]">Assigns balanced leads to North, South, East, West India reps or syncs to HubSpot</p>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Runs History */}
        <div className="p-5 rounded-xl border bg-slate-900/60 border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-400" /> Recent Runs
            </h3>
            <button 
              onClick={() => onNavigate('smart')}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              Upload new
            </button>
          </div>

          <div className="space-y-2">
            {runs.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">
                No pipeline runs recorded yet. Click &quot;Run Demo&quot; to test.
              </div>
            ) : (
              runs.slice(0, 5).map((r) => (
                <div 
                  key={r.run_id}
                  onClick={() => onNavigate('leads')}
                  className="p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/70 border border-slate-800 flex items-center justify-between cursor-pointer transition-colors"
                >
                  <div className="truncate pr-2">
                    <p className="text-xs font-semibold text-white truncate">{r.filename || 'Processed Leads'}</p>
                    <p className="text-[11px] text-slate-400">
                      {r.row_count_out || 0} leads · {r.duplicates_merged || 0} merged
                    </p>
                  </div>
                  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-full ${
                    r.status === 'completed' 
                      ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                      : r.status === 'failed'
                      ? 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                      : 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
                  }`}>
                    {r.status || 'Done'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
