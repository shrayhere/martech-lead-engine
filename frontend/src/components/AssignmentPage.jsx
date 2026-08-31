import React, { useState, useEffect } from 'react';
import { UserCheck, Play, MapPin, Briefcase, Flame, Thermometer, Snowflake, Info, Loader2, Sparkles, CheckCircle2 } from 'lucide-react';

export default function AssignmentPage() {
  const [repsData, setRepsData] = useState([]);
  const [isAssigning, setIsAssigning] = useState(false);
  const [ruleBreakdown, setRuleBreakdown] = useState(null);

  const fetchRepsData = async () => {
    try {
      const res = await fetch('/api/leads/reps');
      if (res.ok) {
        const data = await res.json();
        setRepsData(data.reps || []);
      }
    } catch (err) {
      console.error('Failed to fetch reps overview:', err);
    }
  };

  const runAssignment = async () => {
    setIsAssigning(true);
    try {
      const res = await fetch('/api/leads/assign', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setRuleBreakdown(data.rule_breakdown);
        await fetchRepsData();
      }
    } catch (err) {
      console.error('Lead assignment failed:', err);
    } finally {
      setIsAssigning(false);
    }
  };

  useEffect(() => {
    fetchRepsData();
  }, []);

  const totalAssigned = repsData.reduce((sum, r) => sum + (r.assigned_count || 0), 0);

  const getBandBadge = (score, band) => {
    if (score >= 80 || band === 'Hot') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1 w-fit">
          <Flame className="w-3 h-3 text-rose-400" />
          Hot
        </span>
      );
    } else if (score >= 50 || band === 'Warm') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1 w-fit">
          <Thermometer className="w-3 h-3 text-amber-400" />
          Warm
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1 w-fit">
        <Snowflake className="w-3 h-3 text-sky-400" />
        Cold
      </span>
    );
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Top Banner & Execution */}
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-indigo-400" />
            Stage 4: Automated Sales Rep Assignment Rules Engine
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Routes leads by Territory Match → Industry Specialty → Round-Robin Fallback with clear assignment audit rationale.
          </p>
        </div>

        <button
          onClick={runAssignment}
          disabled={isAssigning}
          className="flex items-center space-x-2 px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white rounded-xl text-sm font-semibold shadow-lg shadow-indigo-500/20 transition-all cursor-pointer disabled:opacity-50"
        >
          {isAssigning ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Routing Leads to Sales Reps...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-white" />
              <span>Run Automated Lead Assignment</span>
            </>
          )}
        </button>
      </div>

      {/* Assignment Rule Priority Order Explanation Box */}
      <div className="glass-panel p-5 rounded-2xl border border-indigo-500/20 bg-indigo-950/20 grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
        <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
          <span className="font-bold text-indigo-300">Rule 1 (Highest Priority)</span>
          <p className="text-slate-300 font-medium">Territory + Industry Match</p>
          <p className="text-[11px] text-slate-500">Rep territory covers lead state AND rep industry specialty matches lead industry.</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
          <span className="font-bold text-cyan-300">Rule 2</span>
          <p className="text-slate-300 font-medium">Territory Match Only</p>
          <p className="text-[11px] text-slate-500">Rep territory list contains lead's normalized state.</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
          <span className="font-bold text-emerald-300">Rule 3</span>
          <p className="text-slate-300 font-medium">Industry Specialty Match</p>
          <p className="text-[11px] text-slate-500">Rep industry specialty matches market segment.</p>
        </div>
        <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 space-y-1">
          <span className="font-bold text-amber-300">Rule 4 (Fallback)</span>
          <p className="text-slate-300 font-medium">Round-Robin Load Balancing</p>
          <p className="text-[11px] text-slate-500">Assigns to eligible sales rep with lowest active lead count.</p>
        </div>
      </div>

      {/* Sales Rep Board / Kanban Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
        {repsData.map((rep) => (
          <div key={rep.id} className="glass-panel p-5 rounded-2xl flex flex-col h-[650px]">
            {/* Rep Card Header */}
            <div className="border-b border-slate-800 pb-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="w-9 h-9 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center font-bold text-indigo-300 text-sm">
                  {rep.name.split(' ').map(n => n[0]).join('')}
                </div>
                <span className="px-2.5 py-1 bg-indigo-500/20 text-indigo-300 text-xs font-bold rounded-lg border border-indigo-500/30">
                  {rep.assigned_count} Leads
                </span>
              </div>
              <div>
                <h3 className="font-bold text-white text-base">{rep.name}</h3>
                <div className="flex items-center gap-1 text-[11px] text-slate-400 mt-0.5">
                  <MapPin className="w-3 h-3 text-cyan-400 shrink-0" />
                  <span>Territory: <strong className="text-slate-200">{rep.territory}</strong></span>
                </div>
                <div className="flex items-center gap-1 text-[11px] text-slate-400 mt-0.5">
                  <Briefcase className="w-3 h-3 text-indigo-400 shrink-0" />
                  <span>Specialty: <strong className="text-indigo-300">{rep.industry_specialty}</strong></span>
                </div>
              </div>
            </div>

            {/* Rep Assigned Leads List */}
            <div className="flex-1 overflow-y-auto mt-4 space-y-3 pr-1">
              {rep.leads && rep.leads.length > 0 ? (
                rep.leads.map((lead) => {
                  const score = lead.active_score ?? lead.rule_score ?? 0;
                  return (
                    <div
                      key={lead.id}
                      className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl space-y-2 hover:border-indigo-500/40 transition-all"
                    >
                      <div className="flex items-center justify-between">
                        {getBandBadge(score, lead.score_band)}
                        <span className="font-mono text-[10px] text-slate-400">{lead.state}</span>
                      </div>

                      <div>
                        <p className="font-bold text-slate-100 text-xs">{lead.first_name} {lead.last_name}</p>
                        <p className="text-[11px] text-slate-400 truncate">{lead.job_title || 'Lead'}</p>
                        <p className="text-[11px] font-semibold text-indigo-300 truncate">{lead.company}</p>
                      </div>

                      {/* Assignment Rationale Badge */}
                      <div className="p-2 bg-slate-900 rounded-lg text-[10px] text-slate-400 border border-slate-800/60 leading-relaxed">
                        <strong className="text-slate-300">Routing Rationale:</strong> {lead.assignment_reason || 'Manual assignment'}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="p-6 text-center text-slate-500 text-xs">
                  No leads assigned yet. Click "Run Automated Lead Assignment" above.
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
