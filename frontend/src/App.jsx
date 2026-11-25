import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import DashboardHome from './components/DashboardHome';
import SmartUploadPage from './components/SmartUploadPage';
import LeadListsPage from './components/LeadListsPage';
import UploadPage from './components/UploadPage';
import DataQualityPage from './components/DataQualityPage';
import ScoringPage from './components/ScoringPage';
import AssignmentPage from './components/AssignmentPage';
import QualityScorePage from './components/QualityScorePage';
import ReviewQueuePage from './components/ReviewQueuePage';
import ClassificationPage from './components/ClassificationPage';
import HubSpotPage from './components/HubSpotPage';
import SettingsPage from './components/SettingsPage';
import LeadDetailDrawer from './components/LeadDetailDrawer';
import RunResultsModal from './components/RunResultsModal';
import LoginModal from './components/LoginModal';
import { Menu, Zap } from 'lucide-react';
import { MountainLogo } from './components/common/ThemeComponents';

// ── Global toast context ─────────────────────────────────────────────────────
let _addToast = () => {};
export function toast(message, type = 'info') { _addToast(message, type); }

function ToastContainer() {
  const [toasts, setToasts] = useState([]);
  _addToast = (message, type) => {
    const id = Date.now();
    setToasts(t => [...t, { id, message, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000);
  };
  if (!toasts.length) return null;
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          {t.type === 'success' && '✓ '}
          {t.type === 'error' && '✕ '}
          {t.message}
        </div>
      ))}
    </div>
  );
}

// ── HubSpot sync status pill (top bar) ──────────────────────────────────────
function HubSpotStatusPill({ onClick }) {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    const load = () => fetch('/api/hubspot/status').then(r => r.ok ? r.json() : null).then(d => d && setStatus(d)).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  if (!status) return null;
  const lastSync = status.last_import?.synced_at;
  const ago = lastSync ? (() => {
    const s = Math.round((Date.now() - new Date(lastSync)) / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    return `${Math.round(s / 3600)}h ago`;
  })() : null;

  return (
    <button
      onClick={onClick}
      title="HubSpot sync status — click to open HubSpot page"
      className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border transition-all cursor-pointer backdrop-blur-md ${
        status.token_configured
          ? 'bg-[#e6ecc9]/15 border-[#e6ecc9]/35 text-[#e6ecc9] hover:bg-[#e6ecc9]/25 shadow-sm'
          : 'bg-white/10 border-white/15 text-[#c9d6d3] hover:bg-white/15'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${status.token_configured ? 'bg-[#e6ecc9]' : 'bg-[#8fa4a1]'}`} />
      <span className="truncate max-w-[150px]">
        {status.token_configured
          ? `HubSpot ${status.workflows_in_db} workflows`
          : 'HubSpot disconnected'}
      </span>
    </button>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [rawLeads, setRawLeads] = useState([]);
  const [cleanLeads, setCleanLeads] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [targetLeadBand, setTargetLeadBand] = useState('all');
  const [pendingReviewCount, setPendingReviewCount] = useState(0);
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(false);

  // Redesign state additions
  const [theme, setTheme] = useState('dark');
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [selectedLeadForDetail, setSelectedLeadForDetail] = useState(null);
  const [latestRunResult, setLatestRunResult] = useState(null);
  const [showResultsModal, setShowResultsModal] = useState(false);
  const [isProcessingDemo, setIsProcessingDemo] = useState(false);

  const checkAuthStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/status');
      if (res.ok) {
        const data = await res.json();
        setIsAuthenticated(data.authenticated);
      } else {
        setIsAuthenticated(false);
      }
    } catch {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
    setShowLoginModal(false);
    fetchRuns();
    fetchCleanLeads();
    fetchReviewCount();
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // ignore
    }
    setIsAuthenticated(false);
    setShowLoginModal(true);
  };

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch('/api/pipeline/runs?limit=30');
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
        if (data.runs?.length > 0 && !selectedRunId) {
          setSelectedRunId(data.runs[0].run_id);
        }
      }
    } catch (e) {
      console.error('Error fetching pipeline runs:', e);
    }
  }, [selectedRunId]);

  const fetchCleanLeads = useCallback(async () => {
    try {
      const res = await fetch('/api/leads/by-band?limit=200');
      if (res.ok) {
        const data = await res.json();
        setCleanLeads(data.leads || []);
      }
    } catch (e) {
      console.error('Error fetching clean leads:', e);
    }
  }, []);

  const fetchReviewCount = useCallback(async () => {
    try {
      const res = await fetch('/api/review?status=pending');
      if (res.ok) {
        const data = await res.json();
        setPendingReviewCount(data.summary?.pending || 0);
      }
    } catch (e) {
      console.error('Error fetching review items:', e);
    }
  }, []);

  useEffect(() => {
    checkAuthStatus();
    const onUnauthorized = () => {
      setIsAuthenticated(false);
      setShowLoginModal(true);
    };
    window.addEventListener('auth:unauthorized', onUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized);
  }, [checkAuthStatus]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchRuns();
      fetchCleanLeads();
      fetchReviewCount();
    }
  }, [isAuthenticated, fetchRuns, fetchCleanLeads, fetchReviewCount]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const handlePipelineCompleted = (newRunId, pipelineResult = null) => {
    setSelectedRunId(newRunId);
    fetchRuns();
    fetchCleanLeads();
    fetchReviewCount();
    if (pipelineResult) {
      setLatestRunResult(pipelineResult);
      setShowResultsModal(true);
    }
    toast('Pipeline execution completed successfully', 'success');
  };

  const handleRunDemo = async () => {
    setIsProcessingDemo(true);
    try {
      const res = await fetch('/api/pipeline/demo', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      handlePipelineCompleted(data.run_id, data);
    } catch (err) {
      toast(`Demo execution failed: ${err.message}`, 'error');
    } finally {
      setIsProcessingDemo(false);
    }
  };

  const handleNavigateToLeads = (band = 'all') => {
    setTargetLeadBand(band);
    setActiveTab('leads');
  };

  return (
    <div className={`min-h-screen flex ${activeTab === 'dashboard' ? 'misty-background' : 'calm-background'} text-[#f3f6f2]`}>
      {/* Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        reviewCount={pendingReviewCount}
        runs={runs}
        isAuthenticated={isAuthenticated}
        onLogout={handleLogout}
        theme={theme}
        toggleTheme={toggleTheme}
        isOpenMobile={isMobileNavOpen}
        setIsOpenMobile={setIsMobileNavOpen}
        extraRight={<HubSpotStatusPill onClick={() => setActiveTab('hubspot')} />}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col lg:pl-64 min-w-0">
        {/* Mobile Top Header */}
        <div className="lg:hidden h-16 border-b border-white/10 flex items-center justify-between px-4 sticky top-0 z-30 backdrop-blur-xl bg-[#122124]/80">
          <button
            onClick={() => setIsMobileNavOpen(true)}
            className="p-1.5 rounded-full text-[#c9d6d3] hover:text-white"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="font-semibold text-sm text-[#f3f6f2] flex items-center gap-2">
            <MountainLogo className="w-4 h-4 text-[#e6ecc9]" />
            MarTech Lead Engine
          </span>
          <HubSpotStatusPill onClick={() => setActiveTab('hubspot')} />
        </div>

        {/* Dynamic Page Content */}
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
          {activeTab === 'dashboard' && (
            <DashboardHome
              runs={runs}
              cleanLeads={cleanLeads}
              onRunDemo={handleRunDemo}
              onNavigate={(tab) => setActiveTab(tab)}
              isProcessingDemo={isProcessingDemo}
            />
          )}
          {activeTab === 'smart' && (
            <SmartUploadPage
              onPipelineComplete={(rId, res) => handlePipelineCompleted(rId, res)}
              onNavigateToLeads={handleNavigateToLeads}
              selectedRunId={selectedRunId}
              onSelectRun={rId => setSelectedRunId(rId)}
            />
          )}
          {activeTab === 'leads' && (
            <LeadListsPage
              initialBand={targetLeadBand}
              selectedRunId={selectedRunId}
              runs={runs}
              onSelectRun={rId => setSelectedRunId(rId)}
              onOpenLeadDetail={(lead) => setSelectedLeadForDetail(lead)}
            />
          )}
          {activeTab === 'upload' && (
            <UploadPage
              onUploadSuccess={fetchCleanLeads}
              rawLeads={rawLeads}
              onProceedToCleaning={() => setActiveTab('quality')}
            />
          )}
          {activeTab === 'quality' && (
            <DataQualityPage onProceedToScoring={() => setActiveTab('scoring')} />
          )}
          {activeTab === 'scoring' && (
            <ScoringPage onProceedToAssignment={() => setActiveTab('assignment')} />
          )}
          {activeTab === 'assignment' && <AssignmentPage />}
          {activeTab === 'dq' && <QualityScorePage runs={runs} defaultRunId={selectedRunId} />}
          {activeTab === 'review' && <ReviewQueuePage runs={runs} onResolved={fetchReviewCount} />}
          {activeTab === 'classify' && <ClassificationPage runs={runs} />}
          {activeTab === 'hubspot' && <HubSpotPage runs={runs} />}
          {activeTab === 'settings' && (
            <SettingsPage
              onSaveSettings={(cfg) => toast('Settings saved successfully', 'success')}
            />
          )}
        </main>

        <footer className="border-t border-white/10 py-5 text-center text-xs text-[#8fa4a1]">
          MarTech Data Quality &amp; Lead Scoring Engine · Autonomous B2B Pipeline
        </footer>
      </div>

      {/* Slide-over Lead Detail Drawer */}
      <LeadDetailDrawer
        lead={selectedLeadForDetail}
        onClose={() => setSelectedLeadForDetail(null)}
      />

      {/* Before / After Execution Modal */}
      <RunResultsModal
        isOpen={showResultsModal}
        onClose={() => setShowResultsModal(false)}
        result={latestRunResult}
        onViewLeads={() => {
          setShowResultsModal(false);
          setActiveTab('leads');
        }}
      />

      {/* Auth Login Modal */}
      <LoginModal
        isOpen={showLoginModal}
        onLoginSuccess={handleLoginSuccess}
      />

      <ToastContainer />
    </div>
  );
}
