import React, { useState } from 'react';
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
  Info
} from 'lucide-react';

export default function SettingsPage({
  defaultCountry = 'India',
  onSaveSettings
}) {
  const [country, setCountry] = useState(defaultCountry);
  const [weights, setWeights] = useState({
    engagement: 35,
    recency: 25,
    title_seniority: 10,
    company_size: 15,
    target_industry: 15,
  });

  const [savedSuccess, setSavedSuccess] = useState(false);

  const totalWeight = Object.values(weights).reduce((a, b) => a + Number(b), 0);

  const handleWeightChange = (key, val) => {
    setWeights(prev => ({ ...prev, [key]: Number(val) }));
    setSavedSuccess(false);
  };

  const handleSave = () => {
    if (onSaveSettings) onSaveSettings({ country, weights });
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fadeIn">
      {/* Page Header */}
      <div>
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-indigo-400" /> Pipeline Settings &amp; Configuration
        </h2>
        <p className="text-sm text-slate-400 mt-1">
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
      <div className="flex items-center justify-end gap-3 pt-2">
        {savedSuccess && (
          <span className="text-xs text-emerald-400 flex items-center gap-1.5 font-semibold">
            <CheckCircle2 className="w-4 h-4" /> Settings updated successfully
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={totalWeight !== 100}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-xs text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors cursor-pointer"
        >
          <Save className="w-4 h-4" />
          <span>Save Preferences</span>
        </button>
      </div>
    </div>
  );
}
