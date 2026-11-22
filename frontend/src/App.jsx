import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header';
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
import LoginModal from './components/LoginModal';

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
      className={`hidden lg:flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border transition-colors cursor-pointer ${
        status.token_configured
          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20'
          : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${status.token_configured ? 'bg-emerald-400' : 'bg-slate-500'}`} />
      {status.token_configured
        ? `HubSpot ${status.workflows_in_db} workflows · synced ${ago || 'never'}`
        : 'HubSpot disconnected'}
    </button>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState('smart');
  const [rawLeads, setRawLeads] = useState([]);
  const [cleanLeads, setCleanLeads] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [targetLeadBand, setTargetLeadBand] = useState('all');
  const [isAuthenticated, setIsAuthenticated] = useState(null); // null = checking, true/false
  const [showLoginModal, setShowLoginModal] = useState(false);

  const checkAuthStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/status');
      if (res.ok) {
        const data = await res.json();
        setIsAuthenticated(Boolean(data.authenticated));
        setShowLoginModal(!data.authenticated);
      } else {
        setIsAuthenticated(false);
        setShowLoginModal(true);
      }
    } catch {
      setIsAuthenticated(false);
      setShowLoginModal(true);
    }
  }, []);

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch {}
    localStorage.removeItem('auth_token');
    setIsAuthenticated(false);
    setShowLoginModal(true);
    toast('Logged out', 'info');
  };

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
    setShowLoginModal(false);
    toast('Access granted', 'success');
    fetchRuns();
    fetchRawLeads();
    fetchCleanLeads();
  };

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch('/api/pipeline/runs');
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
        if (data.runs?.length > 0 && !selectedRunId) {
          setSelectedRunId(data.runs[0].run_id);
        }
      }
    } catch {}
  }, [selectedRunId]);

  const fetchRawLeads = useCallback(async () => {
    try {
      const res = await fetch('/api/leads/raw?limit=10');
      if (res.ok) { const d = await res.json(); setRawLeads(d.leads || []); }
    } catch {}
  }, []);

  const fetchCleanLeads = useCallback(async () => {
    try {
      const res = await fetch('/api/leads/clean?limit=10');
      if (res.ok) { const d = await res.json(); setCleanLeads(d.leads || []); }
    } catch {}
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
      fetchRawLeads();
      fetchCleanLeads();
    }
  }, [isAuthenticated, fetchRuns, fetchRawLeads, fetchCleanLeads]);

  const handlePipelineCompleted = (newRunId) => {
    setSelectedRunId(newRunId);
    fetchRuns();
    fetchRawLeads();
    fetchCleanLeads();
    toast('Pipeline completed successfully', 'success');
  };

  const handleNavigateToLeads = (band = 'all') => {
    setTargetLeadBand(band);
    setActiveTab('leads');
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg)', color: 'var(--text)', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        rawCount={rawLeads.length}
        cleanCount={cleanLeads.length}
        runs={runs}
        selectedRunId={selectedRunId}
        onSelectRun={rId => setSelectedRunId(rId)}
        extraRight={<HubSpotStatusPill onClick={() => setActiveTab('hubspot')} />}
        isAuthenticated={isAuthenticated}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'smart' && (
          <SmartUploadPage
            onPipelineComplete={handlePipelineCompleted}
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
          />
        )}
        {activeTab === 'upload' && (
          <UploadPage
            onUploadSuccess={fetchRawLeads}
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
        {activeTab === 'dq' && <QualityScorePage runs={runs} />}
        {activeTab === 'review' && <ReviewQueuePage runs={runs} />}
        {activeTab === 'classify' && <ClassificationPage runs={runs} />}
        {activeTab === 'hubspot' && <HubSpotPage runs={runs} />}
      </main>

      <footer className="border-t py-5 text-center text-xs" style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}>
        MarTech Data Quality &amp; Lead Scoring Engine · Autonomous B2B Pipeline
      </footer>

      <LoginModal
        isOpen={showLoginModal}
        onLoginSuccess={handleLoginSuccess}
      />

      <ToastContainer />
    </div>
  );
}
