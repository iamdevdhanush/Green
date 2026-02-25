import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { dashboardAPI, machinesAPI } from '../api/client';

function StatCard({ title, value, sub, icon, color = 'green', trend }) {
  const colors = {
    green: { bg: 'var(--green-bg)', border: 'var(--green-border)', text: 'var(--green-primary)' },
    blue: { bg: 'var(--blue-bg)', border: 'rgba(59,130,246,0.2)', text: 'var(--blue-primary)' },
    amber: { bg: 'var(--amber-bg)', border: 'rgba(245,158,11,0.2)', text: 'var(--amber-primary)' },
    red: { bg: 'var(--red-bg)', border: 'rgba(239,68,68,0.2)', text: 'var(--red-primary)' },
    purple: { bg: 'var(--purple-bg)', border: 'rgba(139,92,246,0.2)', text: 'var(--purple-primary)' },
    muted: { bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.2)', text: 'var(--text-muted)' },
  };
  const c = colors[color] || colors.green;

  return (
    <div className="card" style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
      <div style={{
        width: '44px', height: '44px', borderRadius: 'var(--radius-md)',
        background: c.bg, border: `1px solid ${c.border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, color: c.text,
      }}>
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>
          {title}
        </div>
        <div style={{ fontSize: '26px', fontWeight: '700', color: 'var(--text-primary)', lineHeight: 1.2, letterSpacing: '-0.02em' }}>
          {value}
        </div>
        {sub && <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>{sub}</div>}
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '12px 16px', fontSize: '13px',
    }}>
      <p style={{ color: 'var(--text-muted)', marginBottom: '6px', fontWeight: '500' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontWeight: '600' }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(4) : p.value}
        </p>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [trend, setTrend] = useState([]);
  const [topIdle, setTopIdle] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [trendDays, setTrendDays] = useState(7);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, trendRes, topRes] = await Promise.all([
        dashboardAPI.stats(),
        dashboardAPI.energyTrend(trendDays),
        dashboardAPI.topIdle(5),
      ]);
      setStats(statsRes.data);
      setTrend(trendRes.data.data || []);
      setTopIdle(topRes.data || []);
      setLastRefresh(new Date());
      setError('');
    } catch (err) {
      setError('Failed to load dashboard data. Retrying...');
    } finally {
      setLoading(false);
    }
  }, [trendDays]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px', gap: '16px' }}>
        <div className="spinner" />
        <p style={{ color: 'var(--text-muted)' }}>Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="animate-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '28px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', letterSpacing: '-0.03em' }}>Dashboard</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>
            Real-time infrastructure energy monitoring
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {lastRefresh && (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button className="btn btn-secondary btn-sm" onClick={fetchData}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '20px' }}>{error}</div>}

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <StatCard
          title="Total Machines"
          value={stats?.total_machines ?? '—'}
          sub={`${stats?.active_last_24h ?? 0} active in last 24h`}
          color="blue"
          icon={<MonitorIcon />}
        />
        <StatCard
          title="Online"
          value={stats?.online_machines ?? '—'}
          sub="Reporting heartbeats"
          color="green"
          icon={<OnlineIcon />}
        />
        <StatCard
          title="Idle"
          value={stats?.idle_machines ?? '—'}
          sub={`${stats?.average_idle_percentage ?? 0}% avg idle rate`}
          color="amber"
          icon={<IdleIcon />}
        />
        <StatCard
          title="Offline"
          value={stats?.offline_machines ?? '—'}
          sub="No recent heartbeat"
          color="muted"
          icon={<OfflineIcon />}
        />
        <StatCard
          title="Energy Wasted"
          value={stats ? `${stats.total_energy_wasted_kwh.toLocaleString()} kWh` : '—'}
          sub={`${stats?.total_idle_hours ?? 0} idle hours total`}
          color="purple"
          icon={<EnergyIcon />}
        />
        <StatCard
          title="Est. Cost"
          value={stats ? `$${stats.estimated_cost_usd.toLocaleString()}` : '—'}
          sub="Electricity waste cost"
          color="red"
          icon={<CostIcon />}
        />
      </div>

      {/* Charts Row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '20px', marginBottom: '24px' }}>
        {/* Energy Trend */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
            <div>
              <h2 style={{ fontSize: '16px', fontWeight: '600' }}>Energy Waste Trend</h2>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>Daily kWh wasted</p>
            </div>
            <select
              className="input"
              value={trendDays}
              onChange={e => setTrendDays(Number(e.target.value))}
              style={{ width: '120px', padding: '6px 32px 6px 10px', fontSize: '13px' }}
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
            </select>
          </div>
          {trend.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={trend} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="energyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} width={40} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="energy_kwh" name="Energy (kWh)" stroke="#10b981" strokeWidth={2} fill="url(#energyGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No energy data yet" />
          )}
        </div>

        {/* Top Idle */}
        <div className="card">
          <div style={{ marginBottom: '20px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: '600' }}>Top Energy Wasters</h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>By total kWh wasted</p>
          </div>
          {topIdle.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {topIdle.map((m, i) => {
                const maxEnergy = topIdle[0]?.energy_wasted_kwh || 1;
                const pct = (m.energy_wasted_kwh / maxEnergy) * 100;
                return (
                  <Link
                    key={m.id}
                    to={`/machines/${m.id}`}
                    style={{ textDecoration: 'none', display: 'block' }}
                  >
                    <div style={{
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      background: 'var(--bg-tertiary)',
                      cursor: 'pointer',
                      transition: 'background var(--transition)',
                    }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'var(--bg-tertiary)'}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-primary)' }}>
                          {i + 1}. {m.hostname}
                        </span>
                        <span style={{ fontSize: '12px', color: 'var(--green-primary)', fontWeight: '600' }}>
                          {m.energy_wasted_kwh.toFixed(3)} kWh
                        </span>
                      </div>
                      <div style={{ background: 'var(--border)', borderRadius: '3px', height: '4px', overflow: 'hidden' }}>
                        <div style={{ width: `${pct}%`, background: 'var(--green-primary)', height: '100%', borderRadius: '3px', transition: 'width 0.5s ease' }} />
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{m.os_type}</span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>${m.energy_cost_usd.toFixed(2)}</span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <EmptyState message="No idle data yet" />
          )}
        </div>
      </div>

      {/* Quick links */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          Monitor all registered machines and their energy consumption in real-time.
        </p>
        <Link to="/machines" className="btn btn-primary btn-sm">
          View All Machines →
        </Link>
      </div>
    </div>
  );
}

function EmptyState({ message }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '160px', color: 'var(--text-muted)', fontSize: '14px', flexDirection: 'column', gap: '8px' }}>
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 21l-6-6m6 6v-4m0 4h-4M3 3l6 6M3 3v4m0-4h4M21 3l-6 6M21 3v4m0-4h-4M3 21l6-6M3 21v-4m0 4h4"/>
      </svg>
      {message}
    </div>
  );
}

// Icons
const MonitorIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>;
const OnlineIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>;
const IdleIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>;
const OfflineIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>;
const EnergyIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>;
const CostIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>;
