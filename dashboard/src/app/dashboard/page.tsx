'use client';
import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { dashboardAPI } from '@/lib/api';
import ProtectedLayout from '@/components/ProtectedLayout';

interface Stats {
  total_machines: number;
  online_machines: number;
  idle_machines: number;
  offline_machines: number;
  active_last_24h: number;
  total_energy_wasted_kwh: number;
  estimated_cost_usd: number;
  average_idle_percentage: number;
  total_idle_hours: number;
}

interface TrendPoint { date: string; energy_kwh: number; }
interface IdleMachine { id: number; hostname: string; energy_wasted_kwh: number; energy_cost_usd: number; os_type: string; }

const COLORS = {
  blue: { bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.2)', text: '#3b82f6' },
  green: { bg: 'var(--green-dim)', border: 'var(--green-border)', text: 'var(--green)' },
  amber: { bg: 'var(--amber-dim)', border: 'rgba(245,158,11,0.2)', text: 'var(--amber)' },
  muted: { bg: 'var(--muted-dim)', border: 'var(--muted-border)', text: 'var(--text-muted)' },
  accent: { bg: 'var(--accent-dim)', border: 'var(--accent-border)', text: 'var(--accent)' },
  red: { bg: 'var(--red-dim)', border: 'rgba(239,68,68,0.2)', text: 'var(--red)' },
};

function StatCard({ label, value, sub, icon, color = 'green' }: {
  label: string; value: string | number; sub?: string; icon: React.ReactNode;
  color?: keyof typeof COLORS;
}) {
  const c = COLORS[color];
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border)',
      padding: '18px', display: 'flex', gap: '14px', alignItems: 'flex-start',
    }}>
      <div style={{
        width: '36px', height: '36px', flexShrink: 0, borderRadius: 'var(--radius)',
        background: c.bg, border: `1px solid ${c.border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', color: c.text,
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '4px' }}>
          {label}
        </div>
        <div style={{ fontSize: '22px', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.02em', lineHeight: 1 }}>
          {value}
        </div>
        {sub && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>{sub}</div>}
      </div>
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
      padding: '10px 14px', fontSize: '12px', borderRadius: 'var(--radius)',
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>{label}</div>
      <div style={{ color: 'var(--accent)', fontWeight: '600' }}>
        {payload[0]?.value?.toFixed(4)} kWh
      </div>
    </div>
  );
};

function DashboardContent() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [topIdle, setTopIdle] = useState<IdleMachine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [trendDays, setTrendDays] = useState(7);

  const fetchData = useCallback(async () => {
    try {
      const [s, t, idle] = await Promise.all([
        dashboardAPI.stats(),
        dashboardAPI.energyTrend(trendDays),
        dashboardAPI.topIdle(5),
      ]);
      setStats(s.data);
      setTrend(t.data.data || []);
      setTopIdle(idle.data || []);
      setError('');
    } catch {
      setError('Failed to load data.');
    } finally {
      setLoading(false);
    }
  }, [trendDays]);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 30000);
    return () => clearInterval(iv);
  }, [fetchData]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '80px' }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="animate-in">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '4px' }}>
            // greenops / dashboard
          </div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            System Overview<span className="cursor" />
          </h1>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {error && <span style={{ fontSize: '11px', color: 'var(--red)' }}>{error}</span>}
          <button
            onClick={fetchData}
            style={{
              padding: '7px 14px', background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius)', color: 'var(--text-secondary)', fontFamily: 'var(--font)',
              fontSize: '12px', cursor: 'pointer', transition: 'all var(--transition)',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
          >
            ↻ refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '20px' }}>
        <StatCard label="total machines" value={stats?.total_machines ?? '—'} sub={`${stats?.active_last_24h ?? 0} active 24h`} color="blue"
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>} />
        <StatCard label="online" value={stats?.online_machines ?? '—'} sub="heartbeating" color="green"
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>} />
        <StatCard label="idle" value={stats?.idle_machines ?? '—'} sub={`${stats?.average_idle_percentage ?? 0}% avg rate`} color="amber"
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>} />
        <StatCard label="offline" value={stats?.offline_machines ?? '—'} sub="no heartbeat" color="muted"
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>} />
        <StatCard label="energy wasted" value={stats ? `${stats.total_energy_wasted_kwh.toLocaleString()} kWh` : '—'} sub={`${stats?.total_idle_hours ?? 0}h idle total`} color="accent"
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>} />
        <StatCard label="est. cost" value={stats ? `$${stats.estimated_cost_usd.toLocaleString()}` : '—'} sub="electricity waste" color="red"
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>} />
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '16px', marginBottom: '20px' }}>
        {/* Trend chart */}
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '2px' }}>// energy_trend</div>
              <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>Daily kWh Wasted</div>
            </div>
            <select
              value={trendDays}
              onChange={e => setTrendDays(Number(e.target.value))}
              style={{
                padding: '5px 10px', background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius)', color: 'var(--text-secondary)', fontFamily: 'var(--font)',
                fontSize: '12px', outline: 'none', cursor: 'pointer',
              }}
            >
              <option value={7}>7d</option>
              <option value={14}>14d</option>
              <option value={30}>30d</option>
            </select>
          </div>
          {trend.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={trend} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00b4d8" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#00b4d8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'var(--font)' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'var(--font)' }} tickLine={false} axisLine={false} width={40} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="energy_kwh" stroke="#00b4d8" strokeWidth={1.5} fill="url(#grad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
              no data yet
            </div>
          )}
        </div>

        {/* Top idle */}
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '20px' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '2px' }}>// top_wasters</div>
          <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '14px' }}>Energy Leaders</div>
          {topIdle.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {topIdle.map((m, i) => {
                const pct = (m.energy_wasted_kwh / (topIdle[0]?.energy_wasted_kwh || 1)) * 100;
                return (
                  <Link key={m.id} href={`/machines/${m.id}`} style={{ textDecoration: 'none' }}>
                    <div style={{
                      padding: '10px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius)',
                      border: '1px solid transparent', transition: 'border-color var(--transition)', cursor: 'pointer',
                    }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-light)'; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'transparent'; }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{i + 1}. {m.hostname}</span>
                        <span style={{ fontSize: '11px', color: 'var(--accent)', fontWeight: '600' }}>{m.energy_wasted_kwh.toFixed(3)} kWh</span>
                      </div>
                      <div style={{ background: 'var(--border)', borderRadius: '2px', height: '3px' }}>
                        <div style={{ width: `${pct}%`, background: 'var(--accent)', height: '100%', borderRadius: '2px', transition: 'width 0.5s ease' }} />
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{m.os_type}</span>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>${m.energy_cost_usd.toFixed(2)}</span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '160px', color: 'var(--text-muted)', fontSize: '12px' }}>
              no idle data yet
            </div>
          )}
        </div>
      </div>

      {/* Footer link */}
      <div style={{
        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
        padding: '14px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Monitor all registered machines and track energy consumption in real-time.
        </span>
        <Link href="/machines" style={{
          padding: '7px 14px', background: 'var(--accent-dim)', border: '1px solid var(--accent-border)',
          borderRadius: 'var(--radius)', color: 'var(--accent)', fontSize: '12px', textDecoration: 'none',
          fontFamily: 'var(--font)', transition: 'all var(--transition)',
        }}>
          ls /machines →
        </Link>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedLayout>
      <DashboardContent />
    </ProtectedLayout>
  );
}
