import React from 'react';
import { Database, ShieldCheck, Cpu, UserCheck, Sparkles, Layers } from 'lucide-react';

export default function Header({ activeTab, setActiveTab, rawCount, cleanCount }) {
  const tabs = [
    { id: 'upload', label: '1. Data Ingestion', icon: Database },
    { id: 'quality', label: '2. Data Quality & Deduplication', icon: ShieldCheck, badge: rawCount > 0 ? `${rawCount}` : null },
    { id: 'scoring', label: '3. Lead Scoring Engine', icon: Cpu, badge: cleanCount > 0 ? `${cleanCount}` : null },
    { id: 'assignment', label: '4. Rep Assignment Rules', icon: UserCheck },
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
                  v1.0 Pro
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                Data Quality, Fuzzy Deduplication & Lead Scoring Pipeline
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex space-x-1 sm:space-x-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                  <span className="hidden md:inline">{tab.label}</span>
                  {tab.badge && (
                    <span className="ml-1 px-1.5 py-0.5 text-[10px] font-bold bg-indigo-500/20 text-indigo-300 rounded-full border border-indigo-500/30">
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
