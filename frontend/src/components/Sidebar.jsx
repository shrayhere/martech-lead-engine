import React, { useState } from 'react';
import { 
  Home, 
  UploadCloud, 
  GitFork, 
  Database, 
  ShieldCheck, 
  Cpu, 
  UserCheck, 
  Flame, 
  ClipboardCheck, 
  Gauge, 
  Brain, 
  Send, 
  Settings, 
  ChevronDown, 
  ChevronRight, 
  Menu, 
  X, 
  Sparkles, 
  LogOut, 
  Sun, 
  Moon,
  FileDown
} from 'lucide-react';

export default function Sidebar({
  activeTab,
  setActiveTab,
  reviewCount = 0,
  runs = [],
  isAuthenticated,
  onLogout,
  theme = 'dark',
  toggleTheme,
  isOpenMobile,
  setIsOpenMobile,
  extraRight
}) {
  const [pipelineOpen, setPipelineOpen] = useState(true);
  const [insightsOpen, setInsightsOpen] = useState(true);

  const navItems = [
    { id: 'dashboard', label: 'Home', icon: Home },
    { id: 'smart', label: 'Upload', icon: UploadCloud, badge: 'Smart' },
    {
      id: 'pipeline_group',
      label: 'Pipeline',
      icon: GitFork,
      isGroup: true,
      isOpen: pipelineOpen,
      toggle: () => setPipelineOpen(!pipelineOpen),
      subItems: [
        { id: 'upload', label: 'Ingestion', icon: Database, desc: 'Parse & map file' },
        { id: 'quality', label: 'Quality', icon: ShieldCheck, desc: 'Clean & fix errors' },
        { id: 'scoring', label: 'Scoring', icon: Cpu, desc: 'Calculate lead score' },
        { id: 'assignment', label: 'Routing', icon: UserCheck, desc: 'Assign to reps' },
      ]
    },
    { id: 'leads', label: 'Leads', icon: Flame },
    { id: 'review', label: 'Review', icon: ClipboardCheck, badge: reviewCount > 0 ? String(reviewCount) : null, badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
    {
      id: 'insights_group',
      label: 'Insights',
      icon: Gauge,
      isGroup: true,
      isOpen: insightsOpen,
      toggle: () => setInsightsOpen(!insightsOpen),
      subItems: [
        { id: 'dq', label: 'Data Quality', icon: Gauge, desc: 'Pass rates & health' },
        { id: 'classify', label: 'AI Classify', icon: Brain, desc: 'Persona & buying role' },
      ]
    },
    { id: 'hubspot', label: 'Integrations', icon: Send, badge: 'HubSpot' },
    { id: 'settings', label: 'Settings', icon: Settings }
  ];

  const handleSelect = (id) => {
    setActiveTab(id);
    if (setIsOpenMobile) setIsOpenMobile(false);
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div 
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setIsOpenMobile(false)}
        />
      )}

      {/* Main Sidebar */}
      <aside className={`
        fixed top-0 bottom-0 left-0 z-50 w-64 flex flex-col transition-transform duration-300 ease-in-out border-r
        ${isOpenMobile ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0
      `}
      style={{
        background: 'var(--card-bg, #0f172a)',
        borderColor: 'var(--border, #1e293b)'
      }}>
        {/* Brand Header */}
        <div className="h-16 flex items-center justify-between px-5 border-b" style={{ borderColor: 'var(--border, #1e293b)' }}>
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => handleSelect('dashboard')}>
            <div className="h-8 w-8 rounded-lg p-0.5 shadow-md flex items-center justify-center bg-gradient-to-br from-indigo-500 to-teal-400">
              <div className="w-full h-full rounded-[6px] flex items-center justify-center" style={{ background: 'var(--bg, #0b0f19)' }}>
                <Sparkles className="w-4 h-4 text-indigo-400" />
              </div>
            </div>
            <div>
              <span className="font-bold text-sm tracking-tight text-white flex items-center gap-1.5">
                MarTech Engine
                <span className="px-1.5 py-0.2 text-[9px] font-semibold rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">v2.0</span>
              </span>
              <p className="text-[10px] text-slate-400">Lead Quality &amp; Routing</p>
            </div>
          </div>
          <button 
            className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            onClick={() => setIsOpenMobile(false)}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1 text-sm custom-scrollbar">
          {navItems.map((item) => {
            if (item.isGroup) {
              const isSubActive = item.subItems.some(sub => sub.id === activeTab);
              return (
                <div key={item.id} className="pt-2">
                  <button
                    onClick={item.toggle}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg font-medium transition-colors ${
                      isSubActive ? 'text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <item.icon className={`w-4 h-4 ${isSubActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                      <span>{item.label}</span>
                    </div>
                    {item.isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  </button>
                  {item.isOpen && (
                    <div className="ml-5 pl-2 mt-1 space-y-0.5 border-l border-slate-800">
                      {item.subItems.map((sub) => {
                        const isCurrent = activeTab === sub.id;
                        return (
                          <button
                            key={sub.id}
                            onClick={() => handleSelect(sub.id)}
                            className={`w-full flex items-center justify-between px-3 py-1.5 rounded-md text-xs transition-colors text-left ${
                              isCurrent 
                                ? 'bg-indigo-600/20 text-indigo-300 font-semibold border border-indigo-500/30' 
                                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                            }`}
                          >
                            <span>{sub.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            }

            const isActive = activeTab === item.id;
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => handleSelect(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg font-medium transition-all ${
                  isActive
                    ? 'bg-gradient-to-r from-indigo-600/30 to-teal-500/20 text-white font-semibold border border-indigo-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                    item.badgeColor || 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Bottom Actions & User Profile */}
        <div className="p-3 border-t space-y-2" style={{ borderColor: 'var(--border, #1e293b)' }}>
          {extraRight && (
            <div className="pb-1">
              {extraRight}
            </div>
          )}

          <div className="flex items-center justify-between px-2 pt-1">
            <button
              onClick={toggleTheme}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 py-1"
              title="Toggle Dark / Light Mode"
            >
              {theme === 'dark' ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5 text-indigo-400" />}
              <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
            </button>

            <a
              href="/MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"
              download
              className="text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1"
              title="Download Architecture QA PDF"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>Report</span>
            </a>
          </div>

          {isAuthenticated && onLogout && (
            <button
              onClick={onLogout}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-rose-300 hover:bg-rose-500/10 border border-slate-800 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out</span>
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
