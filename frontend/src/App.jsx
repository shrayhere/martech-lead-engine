import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import UploadPage from './components/UploadPage';
import DataQualityPage from './components/DataQualityPage';
import ScoringPage from './components/ScoringPage';
import AssignmentPage from './components/AssignmentPage';

export default function App() {
  const [activeTab, setActiveTab] = useState('upload');
  const [rawLeads, setRawLeads] = useState([]);
  const [cleanLeads, setCleanLeads] = useState([]);

  const fetchRawLeads = async () => {
    try {
      const res = await fetch('/api/leads/raw');
      if (res.ok) {
        const data = await res.json();
        setRawLeads(data.leads || []);
      }
    } catch (err) {
      console.error('Failed to fetch raw leads:', err);
    }
  };

  const fetchCleanLeads = async () => {
    try {
      const res = await fetch('/api/leads/clean');
      if (res.ok) {
        const data = await res.json();
        setCleanLeads(data.leads || []);
      }
    } catch (err) {
      console.error('Failed to fetch clean leads:', err);
    }
  };

  useEffect(() => {
    fetchRawLeads();
    fetchCleanLeads();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        rawCount={rawLeads.length}
        cleanCount={cleanLeads.length}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'upload' && (
          <UploadPage
            onUploadSuccess={fetchRawLeads}
            rawLeads={rawLeads}
            onProceedToCleaning={() => setActiveTab('quality')}
          />
        )}
        {activeTab === 'quality' && (
          <DataQualityPage
            onProceedToScoring={() => setActiveTab('scoring')}
          />
        )}
        {activeTab === 'scoring' && (
          <ScoringPage
            onProceedToAssignment={() => setActiveTab('assignment')}
          />
        )}
        {activeTab === 'assignment' && <AssignmentPage />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-6 text-center text-xs text-slate-500">
        <p>MarTech Data Quality & Lead Scoring Engine • Production-Grade Architecture</p>
      </footer>
    </div>
  );
}
