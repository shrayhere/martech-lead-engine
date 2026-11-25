import React, { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { MountainLogo, CreamButton, GlassPill } from './common/ThemeComponents';

export default function LoginModal({ isOpen, onLoginSuccess }) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password.trim()) {
      setError('Please enter the workspace password');
      return;
    }
    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: password.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed');
      }
      setPassword('');
      onLoginSuccess();
    } catch (err) {
      setError(err.message || 'Invalid password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const featurePills = [
    'Understands any columns',
    'Merges duplicates',
    'Explainable scores',
    'Syncs to HubSpot'
  ];

  return (
    <div className="fixed inset-0 z-[100] overflow-y-auto misty-background flex flex-col justify-between">
      {/* Background artwork light layer */}
      <div 
        className="pointer-events-none absolute inset-0 z-0 opacity-40"
        style={{
          background: `
            radial-gradient(ellipse 60% 40% at 50% 30%, rgba(200, 225, 220, 0.25) 0%, transparent 60%),
            radial-gradient(ellipse 70% 50% at 85% 70%, rgba(18, 38, 42, 0.8) 0%, transparent 70%)
          `
        }}
      />
      <div className="pointer-events-none absolute top-8 right-12 w-48 h-48 dot-grid opacity-30 z-0" />

      {/* Top Navigation Bar */}
      <header className="relative z-10 w-full max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2.5 text-[#f3f6f2]">
          <MountainLogo className="w-6 h-6 text-[#e6ecc9]" />
          <span className="font-semibold text-base sm:text-lg tracking-tight">
            MarTech Lead Engine
          </span>
        </div>

        <div className="flex items-center gap-3">
          <GlassPill onClick={() => {
            const el = document.getElementById('how-it-works-preview');
            if (el) el.scrollIntoView({ behavior: 'smooth' });
          }}>
            How it works
          </GlassPill>
          <GlassPill active className="hidden sm:inline-flex">
            Sign in
          </GlassPill>
        </div>
      </header>

      {/* Hero + Login Grid */}
      <main className="relative z-10 w-full max-w-7xl mx-auto px-6 py-10 lg:py-16 flex-1 flex items-center">
        <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          
          {/* Left Column: Value Proposition & Hero */}
          <div className="lg:col-span-7 space-y-8 animate-fade-in-up">
            <div className="space-y-4">
              <span className="inline-block text-xs font-semibold tracking-[0.2em] text-[#c9d6d3] uppercase">
                B2B Lead Pipeline
              </span>
              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-normal leading-[1.08] text-[#f3f6f2] tracking-tight">
                <span className="font-display text-[#e6ecc9] mr-3">Clean</span> 
                leads,
                <br />
                scored &amp; routed.
              </h1>
              <p className="text-base sm:text-lg text-[#c9d6d3] leading-relaxed max-w-xl font-light">
                Upload any messy lead list. It fixes formats, merges duplicates, scores every lead with clear reasons and sends the best ones to the right rep.
              </p>
            </div>

            {/* Feature Pills */}
            <div className="flex flex-wrap gap-2.5 pt-2">
              {featurePills.map((pill) => (
                <span 
                  key={pill}
                  className="px-4 py-2 rounded-full text-xs sm:text-sm font-medium bg-white/10 backdrop-blur-md border border-white/20 text-[#f3f6f2] shadow-sm"
                >
                  {pill}
                </span>
              ))}
            </div>
          </div>

          {/* Right Column: Centered Glass Login Card */}
          <div className="lg:col-span-5 flex justify-center lg:justify-end">
            <div 
              className="w-full max-w-md p-8 sm:p-10 rounded-[28px] border border-white/20 shadow-2xl backdrop-blur-2xl relative animate-fade-in-up"
              style={{
                background: 'rgba(18, 33, 37, 0.78)',
                boxShadow: '0 24px 64px -12px rgba(0, 0, 0, 0.55)',
              }}
            >
              <div className="mb-6">
                <h2 className="font-display text-3xl sm:text-4xl text-[#f3f6f2] tracking-wide mb-1.5">
                  Welcome back
                </h2>
                <p className="text-xs sm:text-sm text-[#c9d6d3]">
                  Enter the workspace password to continue.
                </p>
              </div>

              {error && (
                <div className="mb-5 flex items-center gap-2.5 p-3 rounded-xl text-xs bg-[#e8a48a]/15 border border-[#e8a48a]/35 text-[#e8a48a]">
                  <AlertCircle className="w-4 h-4 shrink-0 text-[#e8a48a]" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="block text-xs font-medium text-[#c9d6d3] mb-2">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password..."
                    autoFocus
                    className="w-full px-4 py-3 rounded-xl text-sm bg-black/40 border border-white/20 text-[#f3f6f2] placeholder-[#8fa4a1] focus:outline-none focus:border-[#e6ecc9] focus:ring-1 focus:ring-[#e6ecc9] transition-all"
                  />
                </div>

                <CreamButton
                  type="submit"
                  disabled={loading}
                  loading={loading}
                  aria-label="Unlock Dashboard"
                  className="w-full justify-between py-3 px-5 text-sm font-semibold cursor-pointer shadow-lg"
                >
                  Sign in
                </CreamButton>
              </form>

              <div className="mt-8 pt-6 border-t border-white/10 text-center space-y-1">
                <p className="text-[11px] text-[#8fa4a1]">
                  Protected workspace · sessions expire after 7 days
                </p>
                <p className="text-[11px] text-[#c9d6d3]/70">
                  Default access password: <code className="px-1.5 py-0.5 rounded bg-black/40 text-[#e6ecc9] font-mono font-medium">martech2026</code>
                </p>
              </div>
            </div>
          </div>

        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 w-full max-w-7xl mx-auto px-6 py-6 text-center text-xs text-[#8fa4a1]">
        MarTech Lead Engine · Autonomous Data Quality &amp; Lead Routing
      </footer>
    </div>
  );
}
