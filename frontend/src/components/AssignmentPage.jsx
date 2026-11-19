import React, { useState, useEffect } from 'react';
import {
  UserCheck, Play, MapPin, Briefcase, Flame, Thermometer, Snowflake,
  Info, Loader2, Sparkles, CheckCircle2, Edit2, Trash2, Plus, X, Check
} from 'lucide-react';

export default function AssignmentPage() {
  const [repsData, setRepsData] = useState([]);
  const [isAssigning, setIsAssigning] = useState(false);
  const [ruleBreakdown, setRuleBreakdown] = useState(null);
  const [editingRepId, setEditingRepId] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', territory: '', industry_specialty: '' });
  const [showAddModal, setShowAddModal] = useState(false);
  const [newRepForm, setNewRepForm] = useState({ name: '', territory: '', industry_specialty: '' });

  const fetchRepsData = async () => {
    try {
      const res = await fetch('/api/leads/reps');
      if (res.ok) {
        const data = await res.json();
        setRepsData(data.reps || []);
      }
    } catch (err) {
      console.error('Failed to fetch reps overview:', err);
    }
  };

  const runAssignment = async () => {
    setIsAssigning(true);
    try {
      const res = await fetch('/api/leads/assign', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setRuleBreakdown(data.rule_breakdown);
        await fetchRepsData();
      }
    } catch (err) {
      console.error('Lead assignment failed:', err);
    } finally {
      setIsAssigning(false);
    }
  };

  const handleStartEdit = (rep) => {
    setEditingRepId(rep.id);
    setEditForm({ name: rep.name, territory: rep.territory, industry_specialty: rep.industry_specialty });
  };

  const handleSaveEdit = async (repId) => {
    try {
      const res = await fetch(`/api/leads/reps/${repId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      });
      if (res.ok) {
        setEditingRepId(null);
        await fetchRepsData();
      }
    } catch (err) {
      console.error('Failed to save rep:', err);
    }
  };

  const handleDeleteRep = async (repId) => {
    if (!window.confirm('Are you sure you want to delete this sales rep?')) return;
    try {
      const res = await fetch(`/api/leads/reps/${repId}`, { method: 'DELETE' });
      if (res.ok) {
        await fetchRepsData();
      }
    } catch (err) {
      console.error('Failed to delete rep:', err);
    }
  };

  const handleCreateRep = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/leads/reps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRepForm),
      });
      if (res.ok) {
        setShowAddModal(false);
        setNewRepForm({ name: '', territory: '', industry_specialty: '' });
        await fetchRepsData();
      }
    } catch (err) {
      console.error('Failed to create rep:', err);
    }
  };

  useEffect(() => {
    fetchRepsData();
  }, []);

  const totalAssigned = repsData.reduce((sum, r) => sum + (r.assigned_count || 0), 0);

  const getBandBadge = (score, band) => {
    if (score >= 80 || band === 'Hot') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#F97316]/15 text-[#F97316] border border-[#F97316]/30 flex items-center gap-1 w-fit">
          <Flame className="w-3 h-3" />
          Hot
        </span>
      );
    }
    if (score >= 50 || band === 'Warm') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#FACC15]/15 text-[#FACC15] border border-[#FACC15]/30 flex items-center gap-1 w-fit">
          <Thermometer className="w-3 h-3" />
          Warm
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#60A5FA]/15 text-[#60A5FA] border border-[#60A5FA]/30 flex items-center gap-1 w-fit">
        <Snowflake className="w-3 h-3" />
        Cold
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="bg-[#121826] border border-[#1F2937] p-6 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-[#6366F1]" /> Sales Rep Routing Engine
          </h2>
          <p className="text-sm text-[#9CA3AF] mt-1">
            Deterministic 4-tier routing: Territory + Industry Match → Territory Only → Industry Only → Round-Robin Load Balancing.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center space-x-1.5 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-[#E5E7EB] border border-[#1F2937] rounded-xl text-xs font-semibold transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4 text-[#2DD4BF]" />
            <span>Add Sales Rep</span>
          </button>

          <button
            onClick={runAssignment}
            disabled={isAssigning}
            className="flex items-center space-x-2 px-5 py-2.5 bg-[#6366F1] hover:bg-indigo-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-500/20 transition-all cursor-pointer disabled:opacity-50"
          >
            {isAssigning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>Routing Leads...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>Run Routing Engine</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Add Rep Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-[#121826] border border-[#1F2937] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1F2937] pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Plus className="w-4 h-4 text-[#2DD4BF]" /> Add New Sales Rep
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-[#9CA3AF] hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateRep} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[#9CA3AF] mb-1">Rep Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Alex Morgan"
                  value={newRepForm.name}
                  onChange={(e) => setNewRepForm({ ...newRepForm, name: e.target.value })}
                  className="w-full bg-[#0B0F1A] border border-[#1F2937] rounded-xl px-3 py-2 text-sm text-[#E5E7EB] focus:outline-none focus:border-[#6366F1]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#9CA3AF] mb-1">Territory (States / Regions, comma-separated or ALL)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CA, WA, OR or ALL"
                  value={newRepForm.territory}
                  onChange={(e) => setNewRepForm({ ...newRepForm, territory: e.target.value })}
                  className="w-full bg-[#0B0F1A] border border-[#1F2937] rounded-xl px-3 py-2 text-sm text-[#E5E7EB] focus:outline-none focus:border-[#6366F1]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#9CA3AF] mb-1">Industry Specialty</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. SaaS, Fintech, Healthcare IT"
                  value={newRepForm.industry_specialty}
                  onChange={(e) => setNewRepForm({ ...newRepForm, industry_specialty: e.target.value })}
                  className="w-full bg-[#0B0F1A] border border-[#1F2937] rounded-xl px-3 py-2 text-sm text-[#E5E7EB] focus:outline-none focus:border-[#6366F1]"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-slate-800 text-[#9CA3AF] rounded-xl text-xs font-semibold hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#6366F1] hover:bg-indigo-500 text-white rounded-xl text-xs font-bold"
                >
                  Create Rep
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rules & Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Rule 1: Territory + Industry', val: ruleBreakdown ? ruleBreakdown['rule1_territory_and_industry'] : '—', desc: 'Highest priority direct match' },
          { label: 'Rule 2: Territory Only', val: ruleBreakdown ? ruleBreakdown['rule2_territory_only'] : '—', desc: 'State-level geographic routing' },
          { label: 'Rule 3: Industry Only', val: ruleBreakdown ? ruleBreakdown['rule3_industry_only'] : '—', desc: 'Vertical domain alignment' },
          { label: 'Rule 4: Round-Robin Load', val: ruleBreakdown ? ruleBreakdown['rule4_round_robin'] : '—', desc: 'Capacity load-balancing fallback' }
        ].map((item, idx) => (
          <div key={idx} className="bg-[#121826] p-4 rounded-xl border border-[#1F2937]">
            <p className="text-[11px] font-semibold text-[#9CA3AF] uppercase tracking-wider">{item.label}</p>
            <p className="text-xl font-mono font-bold text-white mt-1">{item.val}</p>
            <p className="text-[10px] text-[#9CA3AF] mt-0.5">{item.desc}</p>
          </div>
        ))}
      </div>

      {/* Sales Rep Workload Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {repsData.map((rep) => {
          const isEditing = editingRepId === rep.id;
          return (
            <div
              key={rep.id}
              className="bg-[#121826] border border-[#1F2937] rounded-2xl p-4 flex flex-col h-[520px] transition-all hover:border-[#6366F1]/30"
            >
              {/* Rep Header */}
              <div className="border-b border-[#1F2937] pb-3">
                {isEditing ? (
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      className="w-full bg-[#0B0F1A] border border-[#1F2937] rounded px-2 py-1 text-xs text-white"
                      placeholder="Name"
                    />
                    <input
                      type="text"
                      value={editForm.territory}
                      onChange={(e) => setEditForm({ ...editForm, territory: e.target.value })}
                      className="w-full bg-[#0B0F1A] border border-[#1F2937] rounded px-2 py-1 text-xs text-white"
                      placeholder="Territory"
                    />
                    <input
                      type="text"
                      value={editForm.industry_specialty}
                      onChange={(e) => setEditForm({ ...editForm, industry_specialty: e.target.value })}
                      className="w-full bg-[#0B0F1A] border border-[#1F2937] rounded px-2 py-1 text-xs text-white"
                      placeholder="Specialty"
                    />
                    <div className="flex gap-1 justify-end pt-1">
                      <button
                        onClick={() => setEditingRepId(null)}
                        className="px-2 py-1 bg-slate-800 text-[#9CA3AF] rounded text-[10px]"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleSaveEdit(rep.id)}
                        className="px-2 py-1 bg-emerald-600 text-white rounded text-[10px] font-bold"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-white text-sm truncate">{rep.name}</h4>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleStartEdit(rep)}
                          className="p-1 text-[#9CA3AF] hover:text-indigo-300 transition-colors"
                          title="Edit routing rules"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteRep(rep.id)}
                          className="p-1 text-[#9CA3AF] hover:text-red-400 transition-colors"
                          title="Delete rep"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#6366F1]/20 text-indigo-300 border border-[#6366F1]/30 font-mono">
                          {rep.assigned_count || 0}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-[11px] text-[#9CA3AF] mt-1">
                      <MapPin className="w-3 h-3 text-[#2DD4BF] shrink-0" />
                      <span className="truncate">Territory: <strong className="text-[#E5E7EB]">{rep.territory}</strong></span>
                    </div>
                    <div className="flex items-center gap-1 text-[11px] text-[#9CA3AF] mt-0.5">
                      <Briefcase className="w-3 h-3 text-[#6366F1] shrink-0" />
                      <span className="truncate">Specialty: <strong className="text-indigo-300">{rep.industry_specialty}</strong></span>
                    </div>
                  </>
                )}
              </div>

              {/* Rep Assigned Leads List */}
              <div className="flex-1 overflow-y-auto mt-4 space-y-3 pr-1">
                {rep.leads && rep.leads.length > 0 ? (
                  rep.leads.map((lead) => {
                    const score = lead.active_score ?? lead.rule_score ?? 0;
                    return (
                      <div
                        key={lead.id}
                        className="p-3 bg-[#0B0F1A] border border-[#1F2937] rounded-xl space-y-2 hover:border-[#6366F1]/40 transition-all"
                      >
                        <div className="flex items-center justify-between">
                          {getBandBadge(score, lead.score_band)}
                          <span className="font-mono text-[10px] text-[#9CA3AF]">{lead.state}</span>
                        </div>

                        <div>
                          <p className="font-bold text-[#E5E7EB] text-xs">{lead.first_name} {lead.last_name}</p>
                          <p className="text-[11px] text-[#9CA3AF] truncate">{lead.job_title || 'Lead'}</p>
                          <p className="text-[11px] font-semibold text-indigo-300 truncate">{lead.company}</p>
                        </div>

                        {/* Assignment Rationale Badge */}
                        <div className="p-2 bg-[#121826] rounded-lg text-[10px] text-[#9CA3AF] border border-[#1F2937] leading-relaxed">
                          <strong className="text-[#E5E7EB]">Routing:</strong> {lead.assignment_reason || 'Manual assignment'}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="p-6 text-center text-[#9CA3AF] text-xs">
                    No leads assigned yet. Click "Run Routing Engine" above.
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
