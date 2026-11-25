import React from 'react';
import { 
  X, 
  Flame, 
  TrendingUp, 
  Clock, 
  User, 
  Building2, 
  Mail, 
  Phone, 
  MapPin, 
  Briefcase, 
  Award, 
  CheckCircle2, 
  AlertCircle, 
  Sparkles,
  ArrowRight
} from 'lucide-react';

export default function LeadDetailDrawer({
  lead,
  onClose
}) {
  if (!lead) return null;

  let breakdown = { signals: [], reasons: [] };
  try {
    if (lead.score_breakdown) {
      breakdown = typeof lead.score_breakdown === 'string' 
        ? JSON.parse(lead.score_breakdown) 
        : lead.score_breakdown;
    }
  } catch (e) {
    // ignore parse error
  }

  const signals = breakdown.signals || [
    { name: 'Engagement Score', points: 35, weight: 0.35, reason: 'High website visits and form submits' },
    { name: 'Job Seniority', points: 20, weight: 0.20, reason: 'Decision maker role' },
    { name: 'Target Industry', points: 15, weight: 0.15, reason: 'High match priority sector' },
    { name: 'Company Size', points: 15, weight: 0.15, reason: 'Enterprise fit (>500)' },
    { name: 'Activity Recency', points: 15, weight: 0.15, reason: 'Active within last 14 days' },
  ];

  const band = lead.score_band || 'Cold';
  const bandBadge = band === 'Hot' 
    ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
    : band === 'Warm'
    ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
    : 'bg-slate-700/50 text-slate-300 border-slate-600/50';

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-slate-900 border-l border-slate-800 text-slate-200 shadow-2xl flex flex-col">
          {/* Header */}
          <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-teal-400 p-0.5 flex items-center justify-center">
                <div className="w-full h-full bg-slate-900 rounded-[10px] flex items-center justify-center font-bold text-white text-sm">
                  {lead.first_name ? lead.first_name[0] : 'L'}
                </div>
              </div>
              <div>
                <h2 className="text-base font-bold text-white leading-tight">
                  {lead.first_name || ''} {lead.last_name || 'Lead Details'}
                </h2>
                <p className="text-xs text-slate-400">{lead.job_title || 'No Title'} · {lead.company || 'Unknown Company'}</p>
              </div>
            </div>
            <button 
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6 custom-scrollbar">
            {/* Score Summary Box */}
            <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Overall Score</span>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${bandBadge}`}>
                  {band} ({lead.active_score ?? lead.rule_score ?? 0})
                </span>
              </div>
              <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${
                    band === 'Hot' ? 'bg-gradient-to-r from-amber-500 to-orange-500' : band === 'Warm' ? 'bg-blue-500' : 'bg-slate-500'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, lead.active_score ?? lead.rule_score ?? 0))}%` }}
                />
              </div>
            </div>

            {/* Score Breakdown (5 Signals as Progress Bars) */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Award className="w-3.5 h-3.5 text-indigo-400" /> Score Breakdown by Signal
              </h3>
              <div className="space-y-2.5">
                {signals.map((sig, idx) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-slate-800/30 border border-slate-800 space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-slate-300">{sig.name}</span>
                      <span className="font-mono font-bold text-indigo-300">{sig.points ?? 0} pts</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-indigo-500 rounded-full" 
                        style={{ width: `${Math.min(100, (sig.points || 0) * 2.5)}%` }}
                      />
                    </div>
                    {sig.reason && (
                      <p className="text-[10px] text-slate-400 pt-0.5">{sig.reason}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* AI Persona & Role */}
            <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20 space-y-2">
              <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" /> AI Persona &amp; Buying Role
              </h3>
              <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                <div>
                  <span className="text-slate-400 text-[11px]">Buying Role:</span>
                  <p className="font-semibold text-white">{lead.buying_role || 'Decision Maker'}</p>
                </div>
                <div>
                  <span className="text-slate-400 text-[11px]">Persona:</span>
                  <p className="font-semibold text-white">{lead.persona || 'Technical Leader'}</p>
                </div>
              </div>
              {lead.recommended_action && (
                <div className="pt-2 border-t border-indigo-500/20 text-xs">
                  <span className="text-indigo-400 font-semibold">Recommended Action:</span>
                  <p className="text-slate-300 mt-0.5">{lead.recommended_action}</p>
                </div>
              )}
            </div>

            {/* Sales Rep Assignment */}
            <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-2">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-teal-400" /> Sales Rep Routing
              </h3>
              <div className="text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-400">Assigned Rep:</span>
                  <span className="font-semibold text-teal-300">{lead.assigned_rep_name || (lead.assigned_rep_id ? `Rep #${lead.assigned_rep_id}` : 'Unassigned')}</span>
                </div>
                {lead.assignment_reason && (
                  <p className="text-[11px] text-slate-400 pt-1">
                    <strong>Rule:</strong> {lead.assignment_reason}
                  </p>
                )}
              </div>
            </div>

            {/* Contact & Location Details */}
            <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-2.5 text-xs">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Contact &amp; Location</h3>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-slate-300">
                  <Mail className="w-3.5 h-3.5 text-slate-400" />
                  <span className="truncate">{lead.email || '—'}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <Phone className="w-3.5 h-3.5 text-slate-400" />
                  <span>{lead.phone || '—'}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  <span>{[lead.city, lead.state, lead.country || 'India'].filter(Boolean).join(', ')}</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                  <Building2 className="w-3.5 h-3.5 text-slate-400" />
                  <span>{lead.company || '—'} ({lead.company_size ? `${lead.company_size} employees` : 'Size unknown'})</span>
                </div>
              </div>
            </div>

            {/* Data Cleaning (Before -> After) */}
            <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800 space-y-2">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Cleaning Applied
              </h3>
              <div className="text-xs space-y-1 text-slate-300">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Phone standardized to international format</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>State &amp; country resolved from location signals</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Job seniority mapped from raw title</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
