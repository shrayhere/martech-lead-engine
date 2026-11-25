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
  X, 
  LogOut, 
  Sun, 
  Moon,
  FileDown
} from 'lucide-react';
import { MountainLogo } from './common/ThemeComponents';

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
  const [pipelineOpen, setPipelineOpen] = useState(false);
  const [insightsOpen, setInsightsOpen] = useState(false);

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
    { 
      id: 'review', 
      label: 'Review', 
      icon: ClipboardCheck, 
      badge: reviewCount > 0 ? String(reviewCount) : null, 
      badgeColor: 'bg-[#e6c98a]/20 text-[#e6c98a] border-[#e6c98a]/40' 
    },
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
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-md"
          onClick={() => setIsOpenMobile(false)}
        />
      )}

      {/* Main Frosted Glass Sidebar */}
      <aside 
        className={`
          fixed top-0 bottom-0 left-0 z-50 w-64 flex flex-col transition-all duration-300 ease-in-out
          border-r border-white/10 shadow-2xl
          ${isOpenMobile ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0
        `}
        style={{
          background: 'rgba(18, 33, 37, 0.88)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
        }}
      >
        {/* Brand Header */}
        <div className="h-20 flex items-center justify-between px-5 border-b border-white/10">
          <div 
            className="flex items-center space-x-3 cursor-pointer group" 
            onClick={() => handleSelect('dashboard')}
          >
            <div className="w-9 h-9 rounded-full flex items-center justify-center bg-white/10 border border-white/20 text-[#e6ecc9] group-hover:scale-105 transition-transform shadow-sm">
              <MountainLogo className="w-5 h-5 text-[#e6ecc9]" />
            </div>
            <div>
              <span className="font-medium text-sm tracking-tight text-[#f3f6f2] flex items-center gap-1.5">
                MarTech Engine
                <span className="px-1.5 py-0.5 text-[9px] font-semibold rounded-full bg-[#e6ecc9]/20 text-[#e6ecc9] border border-[#e6ecc9]/30">v2.0</span>
              </span>
              <p className="text-[11px] text-[#c9d6d3]/70 font-light">Lead Engine &amp; Routing</p>
            </div>
          </div>
          <button 
            className="lg:hidden p-1.5 rounded-full text-[#c9d6d3] hover:text-white hover:bg-white/10"
            onClick={() => setIsOpenMobile(false)}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 overflow-y-auto px-3.5 py-5 space-y-1.5 text-sm custom-scrollbar">
          {navItems.map((item) => {
            if (item.isGroup) {
              const isSubActive = item.subItems.some(sub => sub.id === activeTab);
              return (
                <div key={item.id} className="pt-1.5">
                  <button
                    onClick={item.toggle}
                    className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-full font-medium transition-all ${
                      isSubActive 
                        ? 'bg-white/15 text-white border border-white/20' 
                        : 'text-[#c9d6d3] hover:text-[#f3f6f2] hover:bg-white/[0.08]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <item.icon className={`w-4 h-4 ${isSubActive ? 'text-[#e6ecc9]' : 'text-[#c9d6d3]'}`} />
                      <span>{item.label}</span>
                    </div>
                    {item.isOpen ? <ChevronDown className="w-3.5 h-3.5 opacity-70" /> : <ChevronRight className="w-3.5 h-3.5 opacity-70" />}
                  </button>
                  {item.isOpen && (
                    <div className="ml-6 pl-2 mt-1 space-y-1 border-l border-white/15">
                      {item.subItems.map((sub) => {
                        const isCurrent = activeTab === sub.id;
                        return (
                          <button
                            key={sub.id}
                            onClick={() => handleSelect(sub.id)}
                            className={`w-full flex items-center justify-between px-3 py-1.5 rounded-full text-xs transition-all text-left ${
                              isCurrent 
                                ? 'bg-[#e6ecc9] text-[#14282b] font-semibold shadow-sm' 
                                : 'text-[#c9d6d3] hover:text-white hover:bg-white/[0.08]'
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
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-full font-medium transition-all ${
                  isActive
                    ? 'bg-[#e6ecc9] text-[#14282b] font-semibold shadow-md shadow-black/20'
                    : 'text-[#c9d6d3] hover:text-[#f3f6f2] hover:bg-white/[0.08]'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-[#14282b]' : 'text-[#c9d6d3]'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                    isActive 
                      ? 'bg-[#14282b]/15 text-[#14282b] border-[#14282b]/30'
                      : item.badgeColor || 'bg-white/15 text-[#e6ecc9] border-white/20'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Bottom Section: Status, Theme Toggle & Logout */}
        <div className="p-4 border-t border-white/10 space-y-2">
          {extraRight && (
            <div className="pb-1">
              {extraRight}
            </div>
          )}

          <div className="flex items-center justify-between px-2 pt-1">
            <button
              onClick={toggleTheme}
              className="flex items-center gap-1.5 text-xs text-[#c9d6d3] hover:text-white py-1 transition-colors"
              title="Toggle Theme"
            >
              {theme === 'dark' ? <Sun className="w-3.5 h-3.5 text-[#e6c98a]" /> : <Moon className="w-3.5 h-3.5 text-[#9ec3d6]" />}
              <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
            </button>

            <a
              href="/MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"
              download
              className="text-xs text-[#9fb8b5] hover:text-[#e6ecc9] flex items-center gap-1 transition-colors"
              title="Download Architecture QA PDF"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>Report</span>
            </a>
          </div>

          {isAuthenticated && onLogout && (
            <button
              onClick={onLogout}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-full text-xs font-medium text-[#c9d6d3] hover:text-[#e8a48a] hover:bg-white/[0.06] border border-white/10 transition-all cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Log out</span>
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
