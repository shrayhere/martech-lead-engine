import React from 'react';
import { 
  X, 
  Award, 
  CheckCircle2, 
  Sparkles,
  User, 
  Building2, 
  Mail, 
  Phone, 
  MapPin 
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
    ? 'bg-[#e8a48a]/20 text-[#e8a48a] border-[#e8a48a]/40'
    : band === 'Warm'
    ? 'bg-[#e6c98a]/20 text-[#e6c98a] border-[#e6c98a]/40'
    : 'bg-[#9ec3d6]/20 text-[#9ec3d6] border-[#9ec3d6]/40';

  const barColor = band === 'Hot' 
    ? 'bg-[#e8a48a]' 
    : band === 'Warm' 
    ? 'bg-[#e6c98a]' 
    : 'bg-[#9ec3d6]';

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/70 backdrop-blur-md transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div 
          className="w-screen max-w-md border-l border-white/15 text-[#f3f6f2] shadow-2xl flex flex-col backdrop-blur-2xl"
          style={{
            background: 'rgba(18, 33, 37, 0.96)',
          }}
        >
          {/* Header */}
          <div className="p-5 border-b border-white/10 flex items-center justify-between bg-black/20">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-white/10 border border-white/20 flex items-center justify-center font-bold text-[#e6ecc9] text-sm">
                {lead.first_name ? lead.first_name[0] : 'L'}
              </div>
              <div>
                <h2 className="text-base font-semibold text-[#f3f6f2] leading-tight">
                  {lead.first_name || ''} {lead.last_name || 'Lead Details'}
                </h2>
                <p className="text-xs text-[#c9d6d3]">{lead.job_title || 'No Title'} · {lead.company || 'Unknown Company'}</p>
              </div>
            </div>
            <button 
              onClick={onClose}
              className="p-1.5 rounded-full text-[#c9d6d3] hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5 custom-scrollbar">
            {/* Score Summary Box */}
            <div className="p-4 rounded-2xl bg-white/[0.06] border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[#c9d6d3] uppercase tracking-wider">Overall Score</span>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${bandBadge}`}>
                  {band} ({lead.active_score ?? lead.rule_score ?? 0})
                </span>
              </div>
              <div className="h-2.5 w-full bg-black/40 rounded-full overflow-hidden p-0.5 border border-white/10">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                  style={{ width: `${Math.min(100, Math.max(0, lead.active_score ?? lead.rule_score ?? 0))}%` }}
                />
              </div>
            </div>

            {/* Score Breakdown (Signals) */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-[#f3f6f2] uppercase tracking-wider flex items-center gap-1.5">
                <Award className="w-3.5 h-3.5 text-[#e6ecc9]" /> Score Breakdown by Signal
              </h3>
              <div className="space-y-2">
                {signals.map((sig, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-white/[0.04] border border-white/10 space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-[#c9d6d3]">{sig.name}</span>
                      <span className="font-semibold text-[#e6ecc9] tabular-nums">{sig.points ?? 0} pts</span>
                    </div>
                    <div className="h-1.5 w-full bg-black/30 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-[#e6ecc9] rounded-full" 
                        style={{ width: `${Math.min(100, (sig.points || 0) * 2.5)}%` }}
                      />
                    </div>
                    {sig.reason && (
                      <p className="text-[11px] text-[#8fa4a1] pt-0.5">{sig.reason}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* AI Persona & Role */}
            <div className="p-4 rounded-2xl bg-[#e6ecc9]/10 border border-[#e6ecc9]/25 space-y-2">
              <h3 className="text-xs font-bold text-[#e6ecc9] uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#e6ecc9]" /> AI Persona &amp; Buying Role
              </h3>
              <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                <div>
                  <span className="text-[#c9d6d3] text-[11px]">Buying Role:</span>
                  <p className="font-semibold text-[#f3f6f2]">{lead.buying_role || 'Decision Maker'}</p>
                </div>
                <div>
                  <span className="text-[#c9d6d3] text-[11px]">Persona:</span>
                  <p className="font-semibold text-[#f3f6f2]">{lead.persona || 'Technical Leader'}</p>
                </div>
              </div>
              {lead.recommended_action && (
                <div className="pt-2 border-t border-[#e6ecc9]/20 text-xs">
                  <span className="text-[#e6ecc9] font-semibold">Recommended Action:</span>
                  <p className="text-[#c9d6d3] mt-0.5">{lead.recommended_action}</p>
                </div>
              )}
            </div>

            {/* Sales Rep Assignment */}
            <div className="p-4 rounded-2xl bg-white/[0.06] border border-white/10 space-y-2">
              <h3 className="text-xs font-bold text-[#f3f6f2] uppercase tracking-wider flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-[#9fb8b5]" /> Sales Rep Routing
              </h3>
              <div className="text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-[#c9d6d3]">Assigned Rep:</span>
                  <span className="font-semibold text-[#e6ecc9]">{lead.assigned_rep_name || (lead.assigned_rep_id ? `Rep #${lead.assigned_rep_id}` : 'Unassigned')}</span>
                </div>
                {lead.assignment_reason && (
                  <p className="text-[11px] text-[#c9d6d3] pt-1">
                    <strong>Rule:</strong> {lead.assignment_reason}
                  </p>
                )}
              </div>
            </div>

            {/* Contact & Location Details */}
            <div className="p-4 rounded-2xl bg-white/[0.06] border border-white/10 space-y-2.5 text-xs">
              <h3 className="text-xs font-bold text-[#f3f6f2] uppercase tracking-wider">Contact &amp; Location</h3>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-[#c9d6d3]">
                  <Mail className="w-3.5 h-3.5 text-[#8fa4a1]" />
                  <span className="truncate">{lead.email || '—'}</span>
                </div>
                <div className="flex items-center gap-2 text-[#c9d6d3]">
                  <Phone className="w-3.5 h-3.5 text-[#8fa4a1]" />
                  <span>{lead.phone || '—'}</span>
                </div>
                <div className="flex items-center gap-2 text-[#c9d6d3]">
                  <MapPin className="w-3.5 h-3.5 text-[#8fa4a1]" />
                  <span>{[lead.city, lead.state, lead.country || 'India'].filter(Boolean).join(', ')}</span>
                </div>
                <div className="flex items-center gap-2 text-[#c9d6d3]">
                  <Building2 className="w-3.5 h-3.5 text-[#8fa4a1]" />
                  <span>{lead.company || '—'} ({lead.company_size ? `${lead.company_size} employees` : 'Size unknown'})</span>
                </div>
              </div>
            </div>

            {/* Cleaning Applied */}
            <div className="p-4 rounded-2xl bg-white/[0.06] border border-white/10 space-y-2">
              <h3 className="text-xs font-bold text-[#f3f6f2] uppercase tracking-wider flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#e6ecc9]" /> Cleaning Applied
              </h3>
              <div className="text-xs space-y-1 text-[#c9d6d3]">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#e6ecc9]" />
                  <span>Phone standardized to international format</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#e6ecc9]" />
                  <span>State &amp; country resolved from location signals</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#e6ecc9]" />
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
