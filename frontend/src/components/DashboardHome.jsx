import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Flame, 
  ShieldCheck, 
  Copy, 
  Clock, 
  Play, 
  UploadCloud, 
  ArrowRight,
  Sparkles,
  Loader2
} from 'lucide-react';
import { 
  GlassCard, 
  CreamButton, 
  GlassPill, 
  StepCard, 
  CurvedDivider 
} from './common/ThemeComponents';

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
  const rowsIn = latestRun?.row_count_in || (totalLeads + duplicatesMerged) || 0;
  const processingTime = latestRun?.execution_time_seconds ? `${latestRun.execution_time_seconds.toFixed(2)}s` : '0.97s';

  // Dynamic date string: e.g. "WEDNESDAY, 25 NOVEMBER"
  const todayFormatted = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    day: 'numeric',
    month: 'long'
  }).toUpperCase();

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

  // 5 Top KPI Cards matching reference image layout
  const kpis = [
    {
      title: 'Rows in',
      value: rowsIn > 0 ? rowsIn.toLocaleString() : (latestRun ? '0' : '206'),
      subtext: latestRun?.filename || 'messy_leads_test.csv',
    },
    {
      title: 'Clean leads',
      value: totalLeads > 0 ? totalLeads.toLocaleString() : (latestRun ? '0' : '176'),
      subtext: fieldsFixed > 0 ? `${fieldsFixed} fields fixed` : '385 fields fixed',
    },
    {
      title: 'Duplicates merged',
      value: duplicatesMerged > 0 ? duplicatesMerged.toLocaleString() : (latestRun ? '0' : '22'),
      subtext: latestRun?.junk_removed ? `${latestRun.junk_removed} junk rows caught` : '13 junk rows caught',
    },
    {
      title: 'Hot leads routed',
      value: hotLeads > 0 ? hotLeads.toLocaleString() : (latestRun ? '0' : '9'),
      subtext: 'Score 80+ · sent to reps',
    },
    {
      title: afterScore !== undefined ? 'Data Quality Health' : 'Processed in',
      value: afterScore !== undefined ? `${afterScore}%` : processingTime,
      subtext: dqImprovement !== null ? `${dqImprovement > 0 ? '+' : ''}${dqImprovement}% vs uploaded` : '~1 hr of manual work',
    }
  ];

  // 5 Step Explainer Cards matching reference image
  const steps = [
    { num: 1, title: 'Upload', desc: 'Any CSV, any column names' },
    { num: 2, title: 'Clean', desc: 'Fixes phones, states, names' },
    { num: 3, title: 'Merge', desc: 'Finds the same person twice' },
    { num: 4, title: 'Score', desc: '0–100 with the reasons' },
    { num: 5, title: 'Route', desc: 'Right rep, synced to HubSpot' },
  ];

  // Top hot leads list (from real clean leads or styled fallback)
  const topLeadsList = cleanLeads.length > 0 
    ? cleanLeads.filter(l => l.score_band === 'Hot').slice(0, 5)
    : [
        {
          id: 1,
          first_name: 'Sam',
          last_name: 'Gonzalez',
          job_title: 'Chief Technology Officer',
          company: 'HyperGrowth Marketing',
          why: 'Engagement 83 · touched 3 days ago',
          assigned_rep_name: 'Sarah J.',
          active_score: 90.4
        },
        {
          id: 2,
          first_name: 'Samantha',
          last_name: 'Anderson',
          job_title: 'Chief Technology Officer',
          company: 'TechFlow Inc',
          why: 'Engagement 89 · Healthcare IT match',
          assigned_rep_name: 'David R.',
          active_score: 89.4
        },
        {
          id: 3,
          first_name: 'Jonathan',
          last_name: 'Williams',
          job_title: 'Director of Operations',
          company: 'Horizon Financial',
          why: 'Engagement 95 · enterprise size',
          assigned_rep_name: 'Sarah J.',
          active_score: 88.0
        }
      ];

  const totalActive = totalLeads || 176;
  const hotPct = Math.round(((hotLeads || 9) / totalActive) * 100);
  const warmPct = Math.round(((warmLeads || 111) / totalActive) * 100);
  const coldPct = Math.max(0, 100 - hotPct - warmPct);

  return (
    <div className="space-y-10 animate-fade-in-up pb-12">
      {/* ── Greeting Header ─────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pt-2">
        <div className="space-y-2">
          <span className="block text-xs font-semibold tracking-[0.2em] text-[#c9d6d3] uppercase">
            {todayFormatted}
          </span>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-normal leading-[1.08] text-[#f3f6f2] tracking-tight">
            <span className="font-display text-[#e6ecc9] mr-2">Your lead pipeline,</span>
            today.
          </h1>
        </div>

        {/* Action Buttons matching reference image */}
        <div className="flex flex-wrap items-center gap-3">
          <CreamButton 
            onClick={() => onNavigate && onNavigate('smart')}
            className="text-sm px-5 py-2.5 shadow-lg"
          >
            Upload leads
          </CreamButton>

          <GlassPill 
            onClick={onRunDemo}
            disabled={isProcessingDemo}
            className="text-sm px-5 py-2.5"
          >
            {isProcessingDemo ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-[#e6ecc9]" />
                <span>Running demo...</span>
              </>
            ) : (
              <span>Run demo with sample data</span>
            )}
          </GlassPill>
        </div>
      </div>

      {/* ── KPI Row (5 Glass Cards) ─────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5 sm:gap-4">
        {kpis.map((kpi, idx) => (
          <GlassCard 
            key={idx} 
            className="p-5 sm:p-6 flex flex-col justify-between"
            hover={true}
          >
            <span className="text-xs sm:text-sm font-light text-[#c9d6d3]">
              {kpi.title}
            </span>
            <div className="my-2 text-3xl sm:text-4xl font-normal text-[#f3f6f2] tracking-tight tabular-nums">
              {kpi.value}
            </div>
            <span className="text-[11px] sm:text-xs text-[#8fa4a1] truncate">
              {kpi.subtext}
            </span>
          </GlassCard>
        ))}
      </div>

      {/* ── How it works: Step Explainer ─────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-2xl sm:text-3xl font-normal text-[#f3f6f2] tracking-tight">
            <span className="font-display text-[#e6ecc9] mr-2">How it</span>
            works
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 sm:gap-4">
          {steps.map((st) => (
            <StepCard 
              key={st.num}
              stepNumber={st.num}
              title={st.title}
              description={st.desc}
            />
          ))}
        </div>
      </section>

      {/* ── Curved Section Divider ──────────────────────────────────────── */}
      <CurvedDivider />

      {/* ── Bottom Section: Lead bands & Top hot leads ──────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left Column: Lead bands (35% width) */}
        <div className="lg:col-span-5">
          <GlassCard className="p-6 sm:p-7 space-y-6" hover={false}>
            <div>
              <h3 className="font-display text-2xl sm:text-3xl text-[#e6ecc9]">
                Lead bands
              </h3>
              <p className="text-xs sm:text-sm text-[#c9d6d3] mt-0.5">
                {totalActive} active leads
              </p>
            </div>

            {/* Segmented Progress Bar */}
            <div className="space-y-2">
              <div className="h-3 w-full rounded-full bg-black/40 overflow-hidden flex p-0.5 gap-1 border border-white/10">
                <div 
                  style={{ width: `${hotPct}%` }}
                  className="h-full rounded-full bg-[#e8a48a] transition-all duration-500"
                  title={`Hot: ${hotPct}%`}
                />
                <div 
                  style={{ width: `${warmPct}%` }}
                  className="h-full rounded-full bg-[#e6c98a] transition-all duration-500"
                  title={`Warm: ${warmPct}%`}
                />
                <div 
                  style={{ width: `${coldPct}%` }}
                  className="h-full rounded-full bg-[#9ec3d6] transition-all duration-500"
                  title={`Cold: ${coldPct}%`}
                />
              </div>
            </div>

            {/* Legend with Counts */}
            <div className="space-y-3 pt-2 text-xs sm:text-sm">
              <button
                onClick={() => onNavigate && onNavigate('leads')}
                className="w-full flex items-center justify-between text-left group hover:opacity-85 transition-opacity"
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#e8a48a]" />
                  <span className="text-[#f3f6f2] font-medium">Hot · 80–100</span>
                </div>
                <span className="text-[#f3f6f2] font-semibold tabular-nums">
                  {hotLeads || 9}
                </span>
              </button>

              <button
                onClick={() => onNavigate && onNavigate('leads')}
                className="w-full flex items-center justify-between text-left group hover:opacity-85 transition-opacity"
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#e6c98a]" />
                  <span className="text-[#f3f6f2] font-medium">Warm · 50–79</span>
                </div>
                <span className="text-[#f3f6f2] font-semibold tabular-nums">
                  {warmLeads || 111}
                </span>
              </button>

              <button
                onClick={() => onNavigate && onNavigate('leads')}
                className="w-full flex items-center justify-between text-left group hover:opacity-85 transition-opacity"
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#9ec3d6]" />
                  <span className="text-[#f3f6f2] font-medium">Cold · 0–49</span>
                </div>
                <span className="text-[#f3f6f2] font-semibold tabular-nums">
                  {coldLeads || 56}
                </span>
              </button>
            </div>
          </GlassCard>
        </div>

        {/* Right Column: Top hot leads table (65% width) */}
        <div className="lg:col-span-7">
          <GlassCard className="p-6 sm:p-7 space-y-4" hover={false}>
            <div className="flex items-center justify-between">
              <h3 className="font-display text-2xl sm:text-3xl text-[#e6ecc9]">
                Top hot leads
              </h3>
              <button 
                onClick={() => onNavigate && onNavigate('leads')}
                className="text-xs sm:text-sm text-[#c9d6d3] hover:text-[#e6ecc9] flex items-center gap-1 transition-colors group cursor-pointer"
              >
                <span>View all leads</span>
                <span className="group-hover:translate-x-1 transition-transform">→</span>
              </button>
            </div>

            {/* Leads Table */}
            <div className="overflow-x-auto -mx-2">
              <table className="table-calm text-left">
                <thead>
                  <tr>
                    <th>Lead</th>
                    <th>Company</th>
                    <th>Why</th>
                    <th>Rep</th>
                    <th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {topLeadsList.map((lead, idx) => {
                    const leadName = `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || 'Qualified Lead';
                    const score = lead.active_score ? Number(lead.active_score).toFixed(1) : '90.0';
                    const rep = lead.assigned_rep_name || 'Sarah J.';
                    const whyReason = lead.why || lead.assignment_reason || 'High intent activity';

                    return (
                      <tr 
                        key={lead.id || idx}
                        onClick={() => onNavigate && onNavigate('leads')}
                        className="cursor-pointer group"
                      >
                        <td>
                          <div className="font-medium text-[#f3f6f2] group-hover:text-[#e6ecc9] transition-colors">
                            {leadName}
                          </div>
                          {lead.job_title && (
                            <div className="text-[11px] text-[#8fa4a1] truncate max-w-[140px]">
                              {lead.job_title}
                            </div>
                          )}
                        </td>
                        <td>
                          <span className="text-xs text-[#c9d6d3]">
                            {lead.company || 'Enterprise'}
                          </span>
                        </td>
                        <td>
                          <span className="text-xs text-[#c9d6d3] max-w-[160px] truncate block" title={whyReason}>
                            {whyReason}
                          </span>
                        </td>
                        <td>
                          <span className="text-xs text-[#c9d6d3]">
                            {rep}
                          </span>
                        </td>
                        <td>
                          <span className="inline-block px-2.5 py-1 rounded-full text-xs font-semibold bg-[#e8a48a]/20 text-[#e8a48a] border border-[#e8a48a]/40 tabular-nums">
                            {score}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </div>

      </div>
    </div>
  );
}
