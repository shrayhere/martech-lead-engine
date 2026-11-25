import React, { useState } from 'react';
import { Lock, KeyRound, AlertCircle, Loader2 } from 'lucide-react';

export default function LoginModal({ isOpen, onLoginSuccess }) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password.trim()) {
      setError('Please enter the application password');
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

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div
        className="w-full max-w-md rounded-2xl border p-6 sm:p-8 shadow-2xl relative"
        style={{
          background: 'var(--card, #131b2e)',
          borderColor: 'var(--border, #2d3748)',
          color: 'var(--text, #f7fafc)',
        }}
      >
        <div className="flex flex-col items-center text-center mb-6">
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 shadow-lg"
            style={{
              background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(45,212,191,0.2))',
              border: '1px solid rgba(99,102,241,0.3)',
            }}
          >
            <Lock className="w-7 h-7 text-indigo-400" />
          </div>
          <h2 className="text-xl font-bold tracking-tight">Access Required</h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-xs">
            Enter the application password to unlock the MarTech Lead Engine dashboard.
          </p>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 p-3 rounded-lg text-xs bg-rose-500/10 border border-rose-500/30 text-rose-300">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Application Password
            </label>
            <div className="relative">
              <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password..."
                autoFocus
                className="w-full pl-9 pr-3 py-2.5 rounded-xl text-sm bg-slate-900/80 border border-slate-700 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg cursor-pointer"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Verifying...</span>
              </>
            ) : (
              'Unlock Dashboard'
            )}
          </button>
        </form>

        <p className="text-[11px] text-center text-slate-500 mt-5">
          Protected by signed session tokens (JWT) &amp; rate limiting.
        </p>
      </div>
    </div>
  );
}
