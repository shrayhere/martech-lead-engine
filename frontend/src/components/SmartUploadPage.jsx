import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud, CheckCircle2, AlertTriangle, ArrowRight, Loader2, Sparkles,
  SlidersHorizontal, Clock, RefreshCw, Zap, Flame, Snowflake, Layers, Check,
  FileDown, ChevronRight, BarChart3, Database, ShieldCheck
} from 'lucide-react';

const PIPELINE_STAGES = [
  { id: 'parse', label: '1. Parse', desc: 'Encoding & Delimiter' },
  { id: 'map', label: '2. Map', desc: 'Schema Abstraction' },
  { id: 'clean', label: '3. Clean', desc: 'E.164, Casing & Junk' },
  { id: 'dedupe', label: '4. Dedupe', desc: 'RapidFuzz & Hash' },
  { id: 'score', label: '5. Score', desc: 'Rule + ML Engine' },
  { id: 'assign', label: '6. Assign', desc: '4-Tier Rep Routing' },
];

export default function SmartUploadPage({
  onPipelineComplete,
  onNavigateToLeads,
  selectedRunId,
  onSelectRun
}) {
  const [file, setFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStage, setCurrentStage] = useState('init');
  const [progressPercent, setProgressPercent] = useState(0);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // Column Mapping Overrides state
  const [editableMapping, setEditableMapping] = useState({});
  const [isRerunning, setIsRerunning] = useState(false);

  const fileInputRef = useRef(null);
  const pollingRef = useRef(null);

  // Load existing run details if selectedRunId changes
  useEffect(() => {
    if (selectedRunId && (!pipelineResult || pipelineResult.run_id !== selectedRunId)) {
      fetchRunStatus(selectedRunId);
    }
  }, [selectedRunId]);

  const fetchRunStatus = async (runId) => {
    try {
      const res = await fetch(`/api/pipeline/status/${runId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'completed' && data.summary) {
          setPipelineResult({
            run_id: data.run_id,
            summary: data.summary,
            column_mapping: data.column_mapping,
            timings: data.timings
          });
          if (data.column_mapping?.canonical_to_source) {
            setEditableMapping({ ...data.column_mapping.canonical_to_source });
          }
        }
      }
    } catch (err) {
      console.error('Failed to fetch run status:', err);
    }
  };

  // Start pipeline immediately on file selection or drop
  const startPipeline = async (uploadFile, mappingOverride = null) => {
    if (!uploadFile && !selectedRunId) return;

    setIsProcessing(true);
    setError(null);
    setCurrentStage('parse');
    setProgressPercent(10);

    const formData = new FormData();
    if (uploadFile) {
      formData.append('file', uploadFile);
    } else if (selectedRunId) {
      formData.append('run_id', selectedRunId);
    }

    if (mappingOverride) {
      formData.append('mapping_override', JSON.stringify(mappingOverride));
    }

    // Step animation ticker while processing
    let stepTicker = setInterval(() => {
      setProgressPercent((prev) => {
        if (prev < 30) {
          setCurrentStage('map');
          return prev + 15;
        } else if (prev < 55) {
          setCurrentStage('clean');
          return prev + 15;
        } else if (prev < 75) {
          setCurrentStage('dedupe');
          return prev + 12;
        } else if (prev < 90) {
          setCurrentStage('score');
          return prev + 10;
        } else if (prev < 96) {
          setCurrentStage('assign');
          return 96;
        }
        return prev;
      });
    }, 450);

    try {
      const res = await fetch('/api/pipeline/run', {
        method: 'POST',
        body: formData,
      });

      clearInterval(stepTicker);
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Pipeline processing failed');
      }

      setProgressPercent(100);
      setCurrentStage('completed');
      setPipelineResult(data);

      if (data.column_mapping?.canonical_to_source) {
        setEditableMapping({ ...data.column_mapping.canonical_to_source });
      }

      if (onPipelineComplete) {
        onPipelineComplete(data.run_id);
      }
    } catch (err) {
      clearInterval(stepTicker);
      setError(err.message);
      setCurrentStage('error');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      if (!selected.name.toLowerCase().endsWith('.csv')) {
        setError('Please upload a valid CSV file.');
        return;
      }
      setFile(selected);
      startPipeline(selected);
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
      const dropped = e.dataTransfer.files[0];
      if (!dropped.name.toLowerCase().endsWith('.csv')) {
        setError('Please drop a valid CSV file.');
        return;
      }
      setFile(dropped);
      startPipeline(dropped);
    }
  };

  const handleRerunWithMapping = async () => {
    if (!pipelineResult?.run_id) return;
    setIsRerunning(true);
    await startPipeline(file, editableMapping);
    setIsRerunning(false);
  };

  const handleMappingChange = (canonicalField, csvColumn) => {
    setEditableMapping((prev) => ({
      ...prev,
      [canonicalField]: csvColumn === '-- None --' ? null : csvColumn
    }));
  };

  // Unique list: first_name and last_name can both come from "Full Name (Split)"
  const rawAvailableColumns = [...new Set(pipelineResult?.column_mapping?.detected_headers ||
    Object.values(pipelineResult?.column_mapping?.canonical_to_source || {}).filter(Boolean))];

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Top Value Banner */}
      <div className="glass-panel p-6 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border border-indigo-500/20 shadow-xl shadow-indigo-500/5">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 text-xs font-bold border border-indigo-500/30">
              One-Shot Smart Upload
            </span>
            <span className="text-xs text-emerald-400 font-medium flex items-center gap-1">
              <Zap className="w-3.5 h-3.5" /> Fast vectorized execution
            </span>
          </div>
          <h1 className="text-2xl font-extrabold text-white mt-1">
            Autonomous Lead Ingestion & Qualification Pipeline
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Upload ANY CSV with unknown headers or messy rows. Ingestion, 3-tier schema mapping, E.164 normalization, RapidFuzz deduplication, AI scoring & rep assignment run in seconds.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="/api/leads/sample-csv"
            download="martech_sample_leads_200.csv"
            className="flex items-center space-x-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 hover:text-white border border-indigo-500/30 rounded-xl text-xs font-semibold transition-all shadow-md cursor-pointer"
          >
            <FileDown className="w-4 h-4 text-indigo-400" />
            <span>Download Sample CSV</span>
          </a>
        </div>
      </div>

      {/* Drag & Drop Zone (Auto-Starts On Drop) */}
      <div className="glass-panel p-8 rounded-2xl border border-slate-800 space-y-4">
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isProcessing && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all flex flex-col items-center justify-center space-y-4 ${
            isDragging
              ? 'border-indigo-400 bg-indigo-500/15 scale-[1.01]'
              : isProcessing
              ? 'border-indigo-500/50 bg-slate-900/60 cursor-wait'
              : 'border-slate-800 hover:border-indigo-500/50 bg-slate-900/30 hover:bg-slate-900/60'
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".csv"
            className="hidden"
            disabled={isProcessing}
          />

          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600/20 to-cyan-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-inner">
            {isProcessing ? (
              <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
            ) : (
              <UploadCloud className="w-8 h-8" />
            )}
          </div>

          <div>
            <p className="text-base font-bold text-white">
              {isProcessing
                ? 'Processing Smart Pipeline in Real Time...'
                : file
                ? `Uploaded: ${file.name}`
                : 'Drop ANY Leads CSV here to auto-start pipeline'}
            </p>
            <p className="text-xs text-slate-400 mt-1 max-w-lg mx-auto">
              {isProcessing
                ? 'Vectorized operations executing schema detection, RapidFuzz deduplication, and ML lead scoring.'
                : 'Zero setup required. Supports arbitrary column names, comma/semicolon/tab delimiters, and up to 100,000 rows.'}
            </p>
          </div>

          {!isProcessing && (
            <button
              type="button"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all pointer-events-none"
            >
              Browse CSV File
            </button>
          )}
        </div>

        {error && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-xs flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-sm">Pipeline Execution Error</p>
              <p className="mt-0.5">{error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Live Progress Stepper */}
      {(isProcessing || pipelineResult) && (
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              Live Pipeline Execution Stepper
            </span>
            <span className="font-mono text-indigo-300 font-bold">{progressPercent}%</span>
          </div>

          {/* Stepper bar */}
          <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Stage pills */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 pt-2">
            {PIPELINE_STAGES.map((st, idx) => {
              const isPast = progressPercent >= ((idx + 1) * 16.6);
              const isCurrent = isProcessing && currentStage === st.id;
              return (
                <div
                  key={st.id}
                  className={`p-3 rounded-xl border transition-all text-xs ${
                    isPast
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                      : isCurrent
                      ? 'bg-indigo-500/20 border-indigo-500 text-white animate-pulse'
                      : 'bg-slate-900/40 border-slate-800/80 text-slate-500'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold">{st.label}</span>
                    {isPast && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                    {isCurrent && <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />}
                  </div>
                  <p className="text-[10px] text-slate-400">{st.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Completion Summary Card & Lead Bands Quick Jump */}
      {pipelineResult?.summary && (
        <div className="space-y-6">
          <div className="glass-panel p-6 rounded-2xl border border-emerald-500/30 bg-gradient-to-b from-slate-900/80 to-slate-950/80 space-y-6">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-extrabold text-white">Pipeline Execution Completed!</h3>
                  <p className="text-xs text-slate-400">
                    Run ID: <span className="font-mono text-indigo-300">{pipelineResult.run_id}</span> • Total Duration: <span className="text-emerald-300 font-bold">{pipelineResult.summary.total_time_seconds}s</span> ({pipelineResult.summary.total_time_ms} ms)
                  </p>
                </div>
              </div>

              <button
                onClick={() => onNavigateToLeads && onNavigateToLeads('all')}
                className="flex items-center space-x-2 px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-500/25 transition-all cursor-pointer"
              >
                <span>View Qualified Lead Lists</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>

            {/* Metric counters */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {[
                { label: 'Rows In', val: pipelineResult.summary.rows_in, color: 'text-white' },
                { label: 'Clean Rows Out', val: pipelineResult.summary.rows_out, color: 'text-emerald-400' },
                { label: 'Duplicates Merged', val: pipelineResult.summary.duplicates_merged, color: 'text-cyan-400' },
                // Junk rows flagged + rows dropped for having no email and no phone (both wait in Review)
                { label: 'Junk / Rejected', val: (pipelineResult.summary.junk_removed || 0) + (pipelineResult.summary.rejected_rows_count || 0), color: 'text-rose-400' },
                { label: 'Fields Fixed', val: pipelineResult.summary.fields_fixed, color: 'text-amber-400' },
                { label: 'Total Run Time', val: `${pipelineResult.summary.total_time_seconds}s`, color: 'text-indigo-400' },
              ].map((m, idx) => (
                <div key={idx} className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 text-center">
                  <div className={`text-xl font-extrabold font-mono ${m.color}`}>{m.val}</div>
                  <div className="text-[11px] text-slate-400 font-medium mt-1">{m.label}</div>
                </div>
              ))}
            </div>

            {/* Lead Band Distribution Jump Cards */}
            {pipelineResult.summary.distribution && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                <div
                  onClick={() => onNavigateToLeads && onNavigateToLeads('hot')}
                  className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 hover:border-rose-500/60 transition-all cursor-pointer flex items-center justify-between group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-lg bg-rose-500/20 text-rose-400">
                      <Flame className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs text-rose-300 font-semibold">Hot Leads (80 - 100)</div>
                      <div className="text-lg font-bold text-white font-mono">
                        {pipelineResult.summary.distribution.Hot || 0}
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-rose-300 group-hover:translate-x-1 transition-transform flex items-center gap-1 font-semibold">
                    View <ChevronRight className="w-4 h-4" />
                  </span>
                </div>

                <div
                  onClick={() => onNavigateToLeads && onNavigateToLeads('warm')}
                  className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 hover:border-amber-500/60 transition-all cursor-pointer flex items-center justify-between group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-lg bg-amber-500/20 text-amber-400">
                      <Zap className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs text-amber-300 font-semibold">Warm Leads (50 - 79)</div>
                      <div className="text-lg font-bold text-white font-mono">
                        {pipelineResult.summary.distribution.Warm || 0}
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-amber-300 group-hover:translate-x-1 transition-transform flex items-center gap-1 font-semibold">
                    View <ChevronRight className="w-4 h-4" />
                  </span>
                </div>

                <div
                  onClick={() => onNavigateToLeads && onNavigateToLeads('cold')}
                  className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30 hover:border-cyan-500/60 transition-all cursor-pointer flex items-center justify-between group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-lg bg-cyan-500/20 text-cyan-400">
                      <Snowflake className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs text-cyan-300 font-semibold">Cold Leads (0 - 49)</div>
                      <div className="text-lg font-bold text-white font-mono">
                        {pipelineResult.summary.distribution.Cold || 0}
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-cyan-300 group-hover:translate-x-1 transition-transform flex items-center gap-1 font-semibold">
                    View <ChevronRight className="w-4 h-4" />
                  </span>
                </div>
              </div>
            )}

            {/* Stage Latency Timings */}
            {pipelineResult.timings && (
              <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
                <div className="flex items-center gap-2 text-slate-400 mb-2 font-semibold">
                  <Clock className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Stage Execution Timings (ms):</span>
                </div>
                <div className="flex flex-wrap gap-3 font-mono text-[11px] text-slate-300">
                  <span>Parse: <b className="text-white">{pipelineResult.timings.parse_ms}ms</b></span>
                  <span>Map: <b className="text-white">{pipelineResult.timings.map_ms}ms</b></span>
                  <span>Clean: <b className="text-white">{pipelineResult.timings.clean_ms}ms</b></span>
                  <span>Dedupe: <b className="text-white">{pipelineResult.timings.dedupe_ms}ms</b></span>
                  <span>Score: <b className="text-white">{pipelineResult.timings.score_ms}ms</b></span>
                  <span>Assign: <b className="text-white">{pipelineResult.timings.assign_ms}ms</b></span>
                  <span>DB Bulk Persist: <b className="text-white">{pipelineResult.timings.db_bulk_persist_ms}ms</b></span>
                </div>
              </div>
            )}
          </div>

          {/* Editable Column Mapping Panel */}
          {pipelineResult.column_mapping && (
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <SlidersHorizontal className="w-4 h-4 text-indigo-400" />
                    Detected Schema Mappings & Confidence Badges
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Inspect 3-tier inferred mappings. Modify any mapping below to re-run the pipeline with your custom overrides.
                  </p>
                </div>

                <button
                  onClick={handleRerunWithMapping}
                  disabled={isRerunning}
                  className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md transition-all cursor-pointer disabled:opacity-50"
                >
                  {isRerunning ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="w-3.5 h-3.5" />
                  )}
                  <span>Re-run Pipeline with Overrides</span>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 pt-2">
                {[
                  'first_name', 'last_name', 'email', 'phone', 'company',
                  'job_title', 'industry', 'company_size', 'state', 'last_activity_date', 'engagement_score'
                ].map((field) => {
                  const assignedCol = editableMapping[field] || '';
                  const confidence = pipelineResult.column_mapping.confidence_scores?.[field] || 1.0;
                  const tier = pipelineResult.column_mapping.detection_tiers?.[field] || 'Detected';

                  const badgeColor =
                    confidence >= 0.95
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      : confidence >= 0.8
                      ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/30';

                  return (
                    <div key={field} className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono text-slate-300 font-semibold">{field}</span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono border ${badgeColor}`}>
                          {tier} ({Math.round(confidence * 100)}%)
                        </span>
                      </div>

                      <select
                        value={assignedCol || '-- None --'}
                        onChange={(e) => handleMappingChange(field, e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option value="-- None --">-- None / Missing --</option>
                        {rawAvailableColumns.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>

              {pipelineResult.column_mapping.unmapped_columns?.length > 0 && (
                <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800/80 text-xs text-slate-400">
                  <span className="text-slate-300 font-semibold">Preserved in `extra_fields` JSON:</span>{' '}
                  <span className="font-mono text-indigo-300">
                    {pipelineResult.column_mapping.unmapped_columns.join(', ')}
                  </span>
                  <span className="text-[11px] text-slate-500 block mt-0.5">
                    (Zero data loss: all unmapped CSV attributes remain searchable on the lead record)
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
