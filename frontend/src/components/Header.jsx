import React from 'react';
import { Database, ShieldCheck, Cpu, UserCheck, Sparkles, Layers, FileDown, Zap, Flame, Clock } from 'lucide-react';

export default function Header({
  activeTab,
  setActiveTab,
  rawCount,
  cleanCount,
  runs = [],
  selectedRunId,
  onSelectRun
}) {
  const tabs = [
    { id: 'smart', label: 'Smart Upload', icon: Zap, badge: 'Auto' },
    { id: 'leads', label: 'Lead Lists', icon: Flame },
    { id: 'upload', label: '1. Ingestion', icon: Database },
    { id: 'quality', label: '2. Quality & Dedup', icon: ShieldCheck, badge: rawCount > 0 ? `${rawCount}` : null },
    { id: 'scoring', label: '3. Lead Scoring', icon: Cpu, badge: cleanCount > 0 ? `${cleanCount}` : null },
    { id: 'assignment', label: '4. Rep Routing', icon: UserCheck },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Branding */}
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/20 flex items-center justify-center">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-indigo-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-lg text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-cyan-300 to-white">
                  MarTech Engine
                </span>
                <span className="px-2 py-0.5 text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-full">
                  v2.0 Smart
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden lg:block">
                Autonomous Lead Quality & Multi-Tier Scoring Engine
              </p>
            </div>
          </div>

          {/* Navigation Tabs & Run Selector */}
          <div className="flex items-center space-x-2">
            <nav className="flex space-x-1 sm:space-x-1.5 overflow-x-auto py-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all shrink-0 cursor-pointer ${
                      isActive
                        ? 'bg-indigo-600/25 text-indigo-300 border border-indigo-500/50 shadow-sm font-semibold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                    <span>{tab.label}</span>
                    {tab.badge && (
                      <span className="ml-1 px-1.5 py-0.2 text-[9px] font-bold bg-indigo-500/20 text-indigo-300 rounded-full border border-indigo-500/30">
                        {tab.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>

            {/* Direct PDF Report Download Button */}
            <a
              href="/MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"
              download="MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"
              className="flex items-center space-x-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 transition-all shadow-sm"
              title="Download Architecture & QA Report PDF"
            >
              <FileDown className="w-4 h-4 text-emerald-400" />
              <span className="hidden sm:inline">Report (PDF)</span>
            </a>
          </div>
        </div>
      </div>
    </header>
  );
}
