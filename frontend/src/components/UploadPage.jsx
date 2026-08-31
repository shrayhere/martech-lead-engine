import React, { useState, useRef } from 'react';
import { UploadCloud, Download, FileText, CheckCircle2, AlertTriangle, ArrowRight, Loader2, Database, Sparkles, SlidersHorizontal } from 'lucide-react';

export default function UploadPage({ onUploadSuccess, rawLeads, onProceedToCleaning }) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadDetails, setUploadDetails] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
        setUploadError('Please select a valid .csv file.');
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setUploadError(null);
      setUploadDetails(null);
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
      if (!droppedFile.name.toLowerCase().endsWith('.csv')) {
        setUploadError('Please drop a valid .csv file.');
        return;
      }
      setFile(droppedFile);
      setUploadError(null);
      setUploadDetails(null);
    }
  };

  const uploadCSV = async () => {
    if (!file) return;
    setIsUploading(true);
    setUploadError(null);
    setUploadDetails(null);

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

      setUploadDetails(data);
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
            Stage 1: Real-Time Flexible CSV Ingestion
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Accepts any custom B2B lead CSV format with real-time dynamic column mapping and intelligent fallbacks.
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

      {/* Upload Zone & Dynamic Header Mapping Container */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Box */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl space-y-4">
          <h3 className="text-base font-semibold text-white">Upload B2B Leads CSV File</h3>

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
                <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB • Ready for Dynamic Ingestion</p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-slate-200">
                  <span className="text-indigo-400 font-semibold">Click to upload</span> or drag and drop any CSV file
                </p>
                <p className="text-xs text-slate-500 mt-1">Smart column mapping accepts custom header names & missing optional columns</p>
              </div>
            )}
          </div>

          {/* Action Buttons & Success / Error Displays */}
          {uploadError && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Upload Error</p>
                <p className="text-xs mt-0.5 text-rose-200">{uploadError}</p>
              </div>
            </div>
          )}

          {uploadDetails && (
            <div className="p-5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  <div>
                    <p className="font-bold text-white text-sm">
                      Successfully Ingested {uploadDetails.records_ingested} Raw Lead Records!
                    </p>
                    <p className="text-xs text-emerald-300 mt-0.5">
                      Batch ID: <span className="font-mono">{uploadDetails.batch_id}</span> • File: {uploadDetails.filename}
                    </p>
                  </div>
                </div>
                <button
                  onClick={onProceedToCleaning}
                  className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-500/20 transition-all shrink-0 cursor-pointer"
                >
                  <span>Run Data Quality Stage</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>

              {/* Mapped Columns Feedback Badges */}
              {uploadDetails.columns_mapped && (
                <div className="p-3 bg-slate-950/60 rounded-lg border border-emerald-500/20 space-y-1.5 text-xs">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                    <SlidersHorizontal className="w-3.5 h-3.5" />
                    <span>Real-Time Header Mapping Applied:</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {Object.entries(uploadDetails.columns_mapped).map(([schemaKey, mappedHeader]) => (
                      <span key={schemaKey} className="px-2 py-0.5 bg-emerald-500/20 text-emerald-200 text-[10px] rounded-md font-mono border border-emerald-500/30">
                        {schemaKey} ← "{mappedHeader}"
                      </span>
                    ))}
                  </div>
                  {uploadDetails.defaulted_fields && uploadDetails.defaulted_fields.length > 0 && (
                    <p className="text-[11px] text-slate-400 pt-1">
                      Auto-filled missing optional columns: <span className="text-slate-300 font-mono">{uploadDetails.defaulted_fields.join(', ')}</span> (using real-time defaults).
                    </p>
                  )}
                </div>
              )}
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
                  <span>Parsing & Mapping CSV...</span>
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

        {/* Flexible Column Recognition Info Card */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            Smart Header Aliases Recognized
          </h3>
          <p className="text-xs text-slate-400">
            Our real-time engine automatically detects custom header aliases from your sales/marketing CRM export:
          </p>
          <div className="space-y-2 text-xs font-mono max-h-80 overflow-y-auto pr-1">
            {[
              { field: 'Name', aliases: 'Name, Full Name, First Name, Last Name' },
              { field: 'Email', aliases: 'Email, Contact Email, E-mail, Mail' },
              { field: 'Company', aliases: 'Company, Organization, Account, Business' },
              { field: 'Title', aliases: 'Job Title, Title, Role, Position' },
              { field: 'Phone', aliases: 'Phone, Phone Number, Mobile, Cell' },
              { field: 'State', aliases: 'State, Region, Location, Address State' },
              { field: 'Industry', aliases: 'Industry, Vertical, Segment, Sector' },
              { field: 'Size', aliases: 'Company Size, Size, Employees, Headcount' },
              { field: 'Activity', aliases: 'Last Activity Date, Date, Updated At' },
            ].map((item, idx) => (
              <div key={idx} className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80 space-y-1">
                <div className="text-indigo-300 font-semibold">{item.field}</div>
                <div className="text-[10px] text-slate-400 font-sans">{item.aliases}</div>
              </div>
            ))}
          </div>
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
                Showing {rawLeads.length} stored records ready for fuzzy deduplication & normalization.
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
