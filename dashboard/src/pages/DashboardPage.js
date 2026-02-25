import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { dashboardAPI } from '../api/client';

function StatCard({ title, value, sub, color = 'cyan' }) {
  const colors = {
    cyan: 'var(--cyan)',
    green: 'var(--green-primary)',
    amber: 'var(--amber-primary)',
    red: 'var(--red-primary)',
    blue: 'var(--blue-primary)',
    muted: 'var(--text-muted)',
  };
  const c = colors[color] || colors.cyan;
  return (
    <div className="card" style={{ borderLeft:`2px solid ${c}` }}>
      <div style={{ fontSize:'10px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'6px' }}>{title}</div>
      <div style={{ fontSize:'24px', fontWeight:'700', color: c, letterSpacing:'-0.02em', lineHeight:1.2 }}>{value}</div>
      {sub && <div style={{ fontSize:'11px', color:'var(--text-muted)', marginTop:'4px' }}>{sub}</div>}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:'var(--bg-tertiary)', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', padding:'10px 14px', fontSize:'12px' }}>
      <p style={{ color:'var(--text-muted)', marginBottom:'4px' }}>{label}</p>
      {payload.map((p, i) => <p key={i} style={{ color: p.color }}>{p.name}: {typeof p.value === 'number' ? p.value.toFixed(4) : p.value}</p>)}
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
      const [sRes, tRes, topRes] = await Promise.all([
        dashboardAPI.stats(), dashboardAPI.energyTrend(trendDays), dashboardAPI.topIdle(5),
      ]);
      setStats(sRes.data);
      setTrend(tRes.data.data || []);
      setTopIdle(topRes.data || []);
      setLastRefresh(new Date());
      setError('');
    } catch { setError('Failed to load dashboard data.'); }
    finally { setLoading(false); }
  }, [trendDays]);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 30000);
    return () => clearInterval(iv);
  }, [fetchData]);

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', minHeight:'400px', flexDirection:'column', gap:'12px' }}>
      <div className="spinner" />
      <p style={{ color:'var(--text-muted)', fontSize:'12px' }}>loading dashboard...</p>
    </div>
  );

  return (
    <div className="animate-in">
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:'24px' }}>
        <div>
          <div style={{ fontSize:'11px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'4px' }}>
            &gt; /dashboard
          </div>
          <h1 style={{ fontSize:'20px', fontWeight:'700', letterSpacing:'-0.02em', color:'var(--text-primary)' }}>
            System Overview
          </h1>
          {lastRefresh && <p style={{ color:'var(--text-muted)', fontSize:'11px', marginTop:'2px' }}>updated {lastRefresh.toLocaleTimeString()}</p>}
        </div>
        <div style={{ display:'flex', gap:'8px', alignItems:'center' }}>
          <select className="input" value={trendDays} onChange={e => setTrendDays(Number(e.target.value))}
            style={{ width:'110px', padding:'5px 28px 5px 8px', fontSize:'11px' }}>
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
          </select>
          <button className="btn btn-secondary btn-sm" onClick={fetchData}>[ refresh ]</button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom:'16px', fontSize:'12px' }}>{error}</div>}

      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(180px, 1fr))', gap:'12px', marginBottom:'20px' }}>
        <StatCard title="total machines" value={stats?.total_machines ?? '—'} sub={`${stats?.active_last_24h ?? 0} active 24h`} color="cyan" />
        <StatCard title="online" value={stats?.online_machines ?? '—'} sub="live heartbeat" color="green" />
        <StatCard title="idle" value={stats?.idle_machines ?? '—'} sub={`${stats?.average_idle_percentage ?? 0}% avg rate`} color="amber" />
        <StatCard title="offline" value={stats?.offline_machines ?? '—'} sub="no recent heartbeat" color="muted" />
        <StatCard title="energy wasted" value={stats ? `${stats.total_energy_wasted_kwh} kWh` : '—'} sub={`${stats?.total_idle_hours ?? 0}h idle total`} color="blue" />
        <StatCard title="est. cost" value={stats ? `$${stats.estimated_cost_usd}` : '—'} sub="electricity waste" color="red" />
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 340px', gap:'16px', marginBottom:'16px' }}>
        <div className="card">
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'16px' }}>
            <div>
              <div style={{ fontSize:'10px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em' }}>energy waste trend</div>
              <div style={{ fontSize:'13px', fontWeight:'600', color:'var(--text-primary)', marginTop:'2px' }}>Daily kWh wasted</div>
            </div>
          </div>
          {trend.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={trend} margin={{ top:4, right:0, bottom:0, left:0 }}>
                <defs>
                  <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--cyan)" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="var(--cyan)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize:10, fill:'var(--text-muted)', fontFamily:'var(--font)' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize:10, fill:'var(--text-muted)', fontFamily:'var(--font)' }} tickLine={false} axisLine={false} width={40} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="energy_kwh" name="kWh" stroke="var(--cyan)" strokeWidth={2} fill="url(#g)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'160px', color:'var(--text-muted)', fontSize:'12px' }}>
              no energy data yet
            </div>
          )}
        </div>

        <div className="card">
          <div style={{ fontSize:'10px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'4px' }}>top energy wasters</div>
          <div style={{ fontSize:'13px', fontWeight:'600', color:'var(--text-primary)', marginBottom:'16px' }}>By total kWh</div>
          {topIdle.length > 0 ? (
            <div style={{ display:'flex', flexDirection:'column', gap:'8px' }}>
              {topIdle.map((m, i) => {
                const max = topIdle[0]?.energy_wasted_kwh || 1;
                return (
                  <Link key={m.id} to={`/machines/${m.id}`} style={{ textDecoration:'none', display:'block' }}>
                    <div style={{ padding:'8px 10px', borderRadius:'var(--radius-sm)', background:'var(--bg-tertiary)', border:'1px solid var(--border)', cursor:'pointer', transition:'all var(--transition)' }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor='var(--cyan-border)'; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor='var(--border)'; }}
                    >
                      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:'5px' }}>
                        <span style={{ fontSize:'12px', color:'var(--text-primary)' }}>{i+1}. {m.hostname}</span>
                        <span style={{ fontSize:'11px', color:'var(--cyan)' }}>{m.energy_wasted_kwh.toFixed(3)}</span>
                      </div>
                      <div style={{ background:'var(--border)', borderRadius:'1px', height:'3px' }}>
                        <div style={{ width:`${(m.energy_wasted_kwh/max)*100}%`, background:'var(--cyan)', height:'100%', borderRadius:'1px' }} />
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <div style={{ color:'var(--text-muted)', fontSize:'12px', textAlign:'center', padding:'40px 0' }}>no idle data yet</div>
          )}
        </div>
      </div>

      <div className="card" style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 20px' }}>
        <p style={{ color:'var(--text-secondary)', fontSize:'13px' }}>View all registered machines and their real-time energy stats.</p>
        <Link to="/machines" className="btn btn-primary btn-sm">[ view all machines ]</Link>
      </div>
    </div>
  );
}
