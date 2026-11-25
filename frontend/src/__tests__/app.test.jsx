import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Sidebar from '../components/Sidebar';
import LoginModal from '../components/LoginModal';
import DashboardHome from '../components/DashboardHome';
import LeadDetailDrawer from '../components/LeadDetailDrawer';

describe('Sidebar', () => {
  it('renders grouped navigation links, review badge, and switches tabs', () => {
    const setActiveTab = vi.fn();
    const toggleTheme = vi.fn();
    render(
      <Sidebar
        activeTab="dashboard"
        setActiveTab={setActiveTab}
        reviewCount={7}
        runs={[]}
        isAuthenticated={true}
        onLogout={vi.fn()}
        theme="dark"
        toggleTheme={toggleTheme}
        isOpenMobile={false}
        setIsOpenMobile={vi.fn()}
      />
    );

    expect(screen.getByText('MarTech Engine')).toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Upload')).toBeInTheDocument();
    expect(screen.getByText('Leads')).toBeInTheDocument();
    expect(screen.getByText('Review')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Leads'));
    expect(setActiveTab).toHaveBeenCalledWith('leads');

    fireEvent.click(screen.getByText('Light mode'));
    expect(toggleTheme).toHaveBeenCalled();
  });
});

describe('LoginModal', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('submits password and relies on httpOnly cookie without storing token in localStorage', async () => {
    const onLoginSuccess = vi.fn();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, token: 'jwt-should-not-be-stored' }),
    });

    render(<LoginModal isOpen={true} onLoginSuccess={onLoginSuccess} />);

    const input = screen.getByPlaceholderText('Enter password...');
    fireEvent.change(input, { target: { value: 'secret123' } });
    fireEvent.click(screen.getByRole('button', { name: /unlock dashboard/i }));

    await waitFor(() => {
      expect(onLoginSuccess).toHaveBeenCalledTimes(1);
    });
    expect(global.fetch).toHaveBeenCalledWith('/api/auth/login', expect.objectContaining({
      method: 'POST',
    }));
    expect(localStorage.getItem('auth_token')).toBeNull();
  });

  it('displays server error on invalid password', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Invalid application password.' }),
    });

    render(<LoginModal isOpen={true} onLoginSuccess={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('Enter password...'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /unlock dashboard/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid application password.')).toBeInTheDocument();
    });
  });
});

describe('DashboardHome Demo Flow', () => {
  it('triggers demo flow and renders real quality & run metrics', async () => {
    const onRunDemo = vi.fn();
    const onNavigate = vi.fn();

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        before: { score: 55 },
        after: { score: 94 },
      }),
    });

    const runs = [{ run_id: 'run-1', filename: 'sample.csv', status: 'completed', row_count_out: 100, duplicates_merged: 5 }];
    const cleanLeads = [
      { id: 1, score_band: 'Hot' },
      { id: 2, score_band: 'Warm' },
    ];

    render(
      <DashboardHome
        runs={runs}
        cleanLeads={cleanLeads}
        onRunDemo={onRunDemo}
        onNavigate={onNavigate}
        isProcessingDemo={false}
      />
    );

    const demoBtn = screen.getByRole('button', { name: /run demo with sample data/i });
    fireEvent.click(demoBtn);
    expect(onRunDemo).toHaveBeenCalledTimes(1);

    await waitFor(() => {
      expect(screen.getByText('94%')).toBeInTheDocument();
      expect(screen.getByText('+39% vs uploaded')).toBeInTheDocument();
    });
  });
});

describe('LeadDetailDrawer', () => {
  it('renders score breakdown, persona, rep assignment, and closes on click', () => {
    const onClose = vi.fn();
    const lead = {
      first_name: 'Aarav',
      last_name: 'Patel',
      email: 'aarav@acme.in',
      phone: '+919876543210',
      company: 'Acme India',
      job_title: 'VP Engineering',
      state: 'Maharashtra',
      country: 'India',
      active_score: 88,
      score_band: 'Hot',
      buying_role: 'Decision Maker',
      persona: 'Engineering Leader',
      recommended_action: 'Route to senior AE immediately',
      assigned_rep_name: 'Pooja Iyer',
      assignment_reason: 'Territory match: West India',
      score_breakdown: JSON.stringify({
        signals: [
          { name: 'Engagement Score', points: 32, reason: 'High intent' },
          { name: 'Job Seniority', points: 10, reason: 'VP level' },
        ],
      }),
    };

    const { container } = render(<LeadDetailDrawer lead={lead} onClose={onClose} />);

    expect(screen.getByText(/Aarav Patel/)).toBeInTheDocument();
    expect(screen.getByText('Hot (88)')).toBeInTheDocument();
    expect(screen.getByText('Decision Maker')).toBeInTheDocument();
    expect(screen.getByText('Engineering Leader')).toBeInTheDocument();
    expect(screen.getByText('Territory match: West India')).toBeInTheDocument();
    expect(screen.getByText('32 pts')).toBeInTheDocument();

    // Close button in header
    const buttons = container.querySelectorAll('button');
    fireEvent.click(buttons[0]);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
