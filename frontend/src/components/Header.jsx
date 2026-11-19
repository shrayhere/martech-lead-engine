import React from 'react';
import { Database, ShieldCheck, Cpu, UserCheck, Sparkles, FileDown, Zap, Flame, Gauge, ClipboardCheck, Brain, Send } from 'lucide-react';

export default function Header({
  activeTab,
  setActiveTab,
  rawCount,
  cleanCount,
  runs = [],
  selectedRunId,
  onSelectRun,
  extraRight,
}) {
  const tabs = [
    { id: 'smart',      label: 'Smart Upload',    icon: Zap,          badge: 'Auto' },
    { id: 'leads',      label: 'Lead Lists',      icon: Flame },
    { id: 'upload',     label: '1. Ingestion',    icon: Database,     badge: rawCount > 0 ? String(rawCount) : null },
    { id: 'quality',    label: '2. Quality',      icon: ShieldCheck },
    { id: 'scoring',    label: '3. Scoring',      icon: Cpu,          badge: cleanCount > 0 ? String(cleanCount) : null },
    { id: 'assignment', label: '4. Routing',      icon: UserCheck },
    { id: 'dq',         label: 'DQ Score',        icon: Gauge },
    { id: 'review',     label: 'Review',          icon: ClipboardCheck },
    { id: 'classify',   label: 'AI Classify',     icon: Brain },
    { id: 'hubspot',    label: 'HubSpot',         icon: Send },
  ];

  return (
    <header
      className="sticky top-0 z-50 backdrop-blur-md"
      style={{ background: 'rgba(18,24,38,0.90)', borderBottom: '1px solid var(--border)' }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between pt-3 pb-2 gap-3">
          {/* Logo */}
          <div className="flex items-center space-x-3 shrink-0">
            <div
              className="h-9 w-9 rounded-xl p-0.5 shadow-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #6366F1, #2DD4BF)' }}
            >
              <div className="w-full h-full rounded-[10px] flex items-center justify-center" style={{ background: 'var(--bg)' }}>
                <Sparkles className="w-4 h-4" style={{ color: '#6366F1' }} />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span
                  className="font-extrabold text-base tracking-tight bg-clip-text text-transparent"
                  style={{ backgroundImage: 'linear-gradient(90deg, #6366F1, #2DD4BF, #E5E7EB)' }}
                >
                  MarTech Engine
                </span>
                <span
                  className="px-1.5 py-0.5 text-[10px] font-semibold rounded-full border"
                  style={{ background: 'rgba(99,102,241,.12)', color: '#818CF8', borderColor: 'rgba(99,102,241,.25)' }}
                >
                  v2.0
                </span>
              </div>
              <p className="text-xs hidden lg:block" style={{ color: 'var(--muted)' }}>
                Autonomous B2B Lead Engine
              </p>
            </div>
          </div>

          {/* Right side: extra content + PDF button */}
          <div className="flex items-center gap-2 shrink-0">
            {extraRight}
            <a
              href="/MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"
              download
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
              style={{ background: 'rgba(45,212,191,.1)', color: '#2DD4BF', border: '1px solid rgba(45,212,191,.25)' }}
              title="Download Architecture & QA Report PDF"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Report</span>
            </a>
          </div>
        </div>

        {/* Navigation tabs */}
        <div className="pb-2">
          <nav className="flex flex-wrap gap-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all shrink-0 cursor-pointer border"
                  style={isActive ? {
                    background: 'rgba(99,102,241,.18)',
                    color: '#A5B4FC',
                    borderColor: 'rgba(99,102,241,.40)',
                    fontWeight: 600,
                  } : {
                    background: 'transparent',
                    color: 'var(--muted)',
                    borderColor: 'transparent',
                  }}
                  onMouseEnter={e => { if (!isActive) { e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.background = 'rgba(255,255,255,.04)'; } }}
                  onMouseLeave={e => { if (!isActive) { e.currentTarget.style.color = 'var(--muted)'; e.currentTarget.style.background = 'transparent'; } }}
                >
                  <Icon className="w-3.5 h-3.5" style={{ color: isActive ? '#6366F1' : undefined }} />
                  <span>{tab.label}</span>
                  {tab.badge && (
                    <span
                      className="ml-0.5 px-1.5 py-0 text-[9px] font-bold rounded-full border"
                      style={{ background: 'rgba(99,102,241,.18)', color: '#A5B4FC', borderColor: 'rgba(99,102,241,.30)' }}
                    >
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
