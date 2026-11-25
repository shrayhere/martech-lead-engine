import React, { useState, useEffect } from 'react';
import { 
  Settings as SettingsIcon, 
  Globe, 
  Sliders, 
  Users, 
  Plus, 
  Trash2, 
  Save, 
  CheckCircle2, 
  ShieldAlert,
  Info,
  Loader2,
  AlertCircle
} from 'lucide-react';

export default function SettingsPage() {
  const [country, setCountry] = useState('India');
  const [weights, setWeights] = useState({
    engagement: 35,
    recency: 25,
    title_seniority: 10,
    company_size: 15,
    target_industry: 15,
  });

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Fetch settings from API on load
  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetch('/api/settings')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (mounted && data) {
          if (data.country) setCountry(data.country);
          if (data.weights) setWeights(data.weights);
        }
      })
      .catch(err => {
        if (mounted) setErrorMessage('Could not load current settings.');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  const totalWeight = Object.values(weights).reduce((a, b) => a + Number(b), 0);

  const handleWeightChange = (key, val) => {
    setWeights(prev => ({ ...prev, [key]: Number(val) }));
    setSavedSuccess(false);
    setErrorMessage(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setErrorMessage(null);
    setSavedSuccess(false);
    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ country, weights })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to save settings');
      }
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      setErrorMessage(err.message || 'Error saving settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in-up">
      {/* Page Header */}
      <div className="glass-panel p-6 rounded-2xl border border-white/10">
        <h2 className="text-2xl font-normal text-[#f3f6f2] flex items-center gap-2">
          <span className="font-display text-[#e6ecc9]">System</span> settings &amp; weights
        </h2>
        <p className="text-xs text-[#c9d6d3] mt-1">
          Configure default localization standards, scoring signal weights, and sales team assignment routing.
        </p>
      </div>

      {/* Default Country Card */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
        <div className="flex items-center gap-2.5">
          <Globe className="w-4 h-4 text-teal-400" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Default Country &amp; Localization</h3>
        </div>
        <p className="text-xs text-slate-400">
          Used to parse and format phone numbers without an international country code (+91, +1, +49) to E.164.
        </p>

        <div className="max-w-xs">
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">Default Phone Region</label>
          <select
            value={country}
            onChange={(e) => {
              setCountry(e.target.value);
              setSavedSuccess(false);
            }}
            className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
          >
            <option value="India">India (+91, standardizes mobile numbers &amp; full state names)</option>
            <option value="United States">United States (+1, converts states to 2-letter codes)</option>
            <option value="Germany">Germany (+49)</option>
            <option value="United Kingdom">United Kingdom (+44)</option>
            <option value="Canada">Canada (+1)</option>
          </select>
        </div>
      </div>

      {/* Scoring Weights Card */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Sliders className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Calibrated Scoring Weights</h3>
          </div>
          <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full border ${
            totalWeight === 100 
              ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20' 
              : 'bg-rose-500/10 text-rose-300 border-rose-500/20'
          }`}>
            Total: {totalWeight}% (must equal 100%)
          </span>
        </div>
        <p className="text-xs text-slate-400">
          Fine-tune the relative importance of firmographic and behavioral signals across all scored leads.
        </p>

        <div className="space-y-4 pt-2">
          {[
            { key: 'engagement', label: 'Engagement Score', desc: 'Form fills, page views, and activity volume' },
            { key: 'recency', label: 'Activity Recency', desc: 'Days since last touchpoint' },
            { key: 'company_size', label: 'Company Employee Size', desc: 'ICP fit based on company scale' },
            { key: 'target_industry', label: 'Target Industry Priority', desc: 'Tech, SaaS, Healthcare, Finance fit' },
            { key: 'title_seniority', label: 'Job Seniority & Decision Authority', desc: 'CXO, Owner, VP, Director vs Junior' },
          ].map(({ key, label, desc }) => (
            <div key={key} className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <div>
                  <span className="font-semibold text-white">{label}</span>
                  <span className="text-slate-400 ml-2">({desc})</span>
                </div>
                <span className="font-mono font-bold text-indigo-400">{weights[key]}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="50"
                step="5"
                value={weights[key]}
                onChange={(e) => handleWeightChange(key, e.target.value)}
                className="w-full accent-indigo-500 bg-slate-800 rounded-lg h-2 cursor-pointer"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Save Button */}
      <div className="flex flex-col sm:flex-row items-end sm:items-center justify-end gap-3 pt-2">
        {errorMessage && (
          <span className="text-xs text-rose-400 flex items-center gap-1.5 font-semibold">
            <AlertCircle className="w-4 h-4 shrink-0" /> {errorMessage}
          </span>
        )}
        {savedSuccess && (
          <span className="text-xs text-emerald-400 flex items-center gap-1.5 font-semibold">
            <CheckCircle2 className="w-4 h-4 shrink-0" /> Settings updated successfully
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={saving || totalWeight !== 100}
          className="flex items-center gap-2 px-6 py-2.5 rounded-full font-semibold text-xs text-[#14282b] bg-[#e6ecc9] hover:bg-[#dce3b8] disabled:opacity-50 transition-all shadow-md cursor-pointer"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin text-[#14282b]" /> : <Save className="w-4 h-4" />}
          <span>{saving ? 'Saving Preferences…' : 'Save Preferences'}</span>
        </button>
      </div>
    </div>
  );
}
