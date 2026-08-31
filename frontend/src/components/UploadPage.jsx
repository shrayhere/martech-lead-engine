import React, { useState, useRef } from 'react';
import { UploadCloud, Download, FileText, CheckCircle2, AlertTriangle, ArrowRight, Loader2, Database } from 'lucide-react';

export default function UploadPage({ onUploadSuccess, rawLeads, onProceedToCleaning }) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        setUploadError('Please select a valid .csv file.');
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setUploadError(null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (!droppedFile.name.endsWith('.csv')) {
        setUploadError('Please drop a valid .csv file.');
        return;
      }
      setFile(droppedFile);
      setUploadError(null);
    }
  };

  const uploadCSV = async () => {
    if (!file) return;
    setIsUploading(true);
    setUploadError(null);
    setUploadSuccessMsg(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/leads/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      setUploadSuccessMsg(`Successfully ingested ${data.records_ingested} raw lead records (Batch ID: ${data.batch_id})`);
      setFile(null);
      if (onUploadSuccess) onUploadSuccess();
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const downloadSampleCSV = () => {
    window.location.href = '/api/leads/sample-csv';
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Top Banner & Sample Download */}
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-400" />
            Stage 1: Lead Data Ingestion
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Upload your raw B2B marketing/sales lead CSV to inspect, validate, and store raw records.
          </p>
        </div>
        <button
          onClick={downloadSampleCSV}
          className="flex items-center space-x-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 hover:text-white border border-indigo-500/30 rounded-xl text-sm font-semibold transition-all shadow-md hover:shadow-indigo-500/10 cursor-pointer"
        >
          <Download className="w-4 h-4 text-indigo-400" />
          <span>Download Sample CSV (200 Leads)</span>
        </button>
      </div>

      {/* Upload Zone & Instructions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Box */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl space-y-4">
          <h3 className="text-base font-semibold text-white">Upload B2B Leads File</h3>

          {/* Drag & Drop Container */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center space-y-3 ${
              isDragging
                ? 'border-indigo-500 bg-indigo-500/10 scale-[1.01]'
                : file
                ? 'border-indigo-500/50 bg-slate-900/50'
                : 'border-slate-800 hover:border-indigo-500/40 bg-slate-900/30 hover:bg-slate-900/60'
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".csv"
              className="hidden"
            />
            <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <UploadCloud className="w-6 h-6" />
            </div>

            {file ? (
              <div>
                <p className="text-sm font-semibold text-indigo-300">{file.name}</p>
                <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB • Ready to Ingest</p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-slate-200">
                  <span className="text-indigo-400 font-semibold">Click to upload</span> or drag and drop CSV file
                </p>
                <p className="text-xs text-slate-500 mt-1">Supports standard CSV format up to 20MB</p>
              </div>
            )}
          </div>

          {/* Action Button & Messages */}
          {uploadError && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Validation Error</p>
                <p className="text-xs mt-0.5 text-rose-200">{uploadError}</p>
              </div>
            </div>
          )}

          {uploadSuccessMsg && (
            <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                <p className="text-xs sm:text-sm font-medium">{uploadSuccessMsg}</p>
              </div>
              <button
                onClick={onProceedToCleaning}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shadow-md transition-all shrink-0 cursor-pointer"
              >
                <span>Run Data Cleaning</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            {file && (
              <button
                onClick={() => setFile(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold cursor-pointer"
              >
                Clear Selection
              </button>
            )}
            <button
              onClick={uploadCSV}
              disabled={!file || isUploading}
              className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                !file || isUploading
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-800'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30 cursor-pointer'
              }`}
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Ingesting CSV...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" />
                  <span>Ingest Raw Leads</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Expected Schema Card */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <FileText className="w-4 h-4 text-indigo-400" />
            Required CSV Columns
          </h3>
          <p className="text-xs text-slate-400">
            The ingestion pipeline automatically validates the presence of these core schema attributes:
          </p>
          <ul className="space-y-2 text-xs font-mono">
            {[
              { col: 'first_name, last_name', desc: 'Lead full name' },
              { col: 'email', desc: 'Primary contact email' },
              { col: 'company', desc: 'Company organization name' },
              { col: 'job_title', desc: 'Title for seniority detection' },
              { col: 'phone', desc: 'Contact phone number' },
              { col: 'state', desc: 'Location / territory state' },
              { col: 'industry', desc: 'Market segment industry' },
              { col: 'company_size', desc: 'Employee count integer' },
              { col: 'engagement_score', desc: 'Behavioral activity (0-100)' },
              { col: 'last_activity_date', desc: 'YYYY-MM-DD timestamp' },
            ].map((item, idx) => (
              <li key={idx} className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/80 flex items-center justify-between">
                <span className="text-indigo-300 font-semibold">{item.col}</span>
                <span className="text-[10px] text-slate-500 font-sans">{item.desc}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Raw Ingested Records Preview Table */}
      {rawLeads && rawLeads.length > 0 && (
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Database className="w-4 h-4 text-indigo-400" />
                Raw Database Records (`raw_leads` table)
              </h3>
              <p className="text-xs text-slate-400">
                Showing {rawLeads.length} stored uncleaned records ready for fuzzy deduplication & normalization.
              </p>
            </div>
            <button
              onClick={onProceedToCleaning}
              className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-500/20 transition-all cursor-pointer"
            >
              <span>Proceed to Stage 2: Data Quality</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="p-3">ID</th>
                  <th className="p-3">Name</th>
                  <th className="p-3">Email</th>
                  <th className="p-3">Company</th>
                  <th className="p-3">Job Title</th>
                  <th className="p-3">Phone</th>
                  <th className="p-3">State</th>
                  <th className="p-3">Industry</th>
                  <th className="p-3">Engagement</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                {rawLeads.slice(0, 15).map((lead) => (
                  <tr key={lead.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="p-3 font-mono text-slate-500">{lead.id}</td>
                    <td className="p-3 font-medium text-slate-200">{lead.first_name || '-'} {lead.last_name || '-'}</td>
                    <td className="p-3 text-indigo-300">{lead.email || <span className="text-rose-400 italic">missing</span>}</td>
                    <td className="p-3 text-slate-300 font-medium">{lead.company || '-'}</td>
                    <td className="p-3 text-slate-400">{lead.job_title || '-'}</td>
                    <td className="p-3 font-mono text-slate-400">{lead.phone || <span className="text-rose-400 italic">missing</span>}</td>
                    <td className="p-3 text-slate-400">{lead.state || '-'}</td>
                    <td className="p-3 text-slate-400">{lead.industry || '-'}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 rounded-full font-mono font-semibold">
                        {lead.engagement_score ?? 0}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rawLeads.length > 15 && (
            <p className="text-center text-xs text-slate-500 pt-1">
              + {rawLeads.length - 15} more raw lead records stored in database
            </p>
          )}
        </div>
      )}
    </div>
  );
}
