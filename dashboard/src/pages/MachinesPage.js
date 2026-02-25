import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { machinesAPI } from '../api/client';

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status}</span>;
}

function fmtIdle(s) {
  if (!s) return '—';
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function MachinesPage() {
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [deleting, setDeleting] = useState(null);
  const [sortKey, setSortKey] = useState('last_seen');
  const [sortDir, setSortDir] = useState('desc');

  const fetchMachines = useCallback(async () => {
    try {
      const params = { limit: 500 };
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;
      const { data } = await machinesAPI.list(params);
      setMachines(data);
      setError('');
    } catch { setError('Failed to load machines.'); }
    finally { setLoading(false); }
  }, [statusFilter, search]);

  useEffect(() => {
    fetchMachines();
    const iv = setInterval(fetchMachines, 30000);
    return () => clearInterval(iv);
  }, [fetchMachines]);

  const handleDelete = async (id, hostname) => {
    if (!window.confirm(`Delete "${hostname}" and all its data?`)) return;
    setDeleting(id);
    try {
      await machinesAPI.delete(id);
      setMachines(prev => prev.filter(m => m.id !== id));
    } catch { setError('Failed to delete machine.'); }
    finally { setDeleting(null); }
  };

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const sorted = [...machines].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    if (av < bv) return sortDir === 'asc' ? -1 : 1;
    if (av > bv) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const SortIcon = ({ k }) => <span style={{ marginLeft:'3px', opacity: sortKey === k ? 1 : 0.3, fontSize:'10px' }}>{sortKey === k ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}</span>;

  return (
    <div className="animate-in">
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:'20px' }}>
        <div>
          <div style={{ fontSize:'11px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'4px' }}>&gt; /machines</div>
          <h1 style={{ fontSize:'20px', fontWeight:'700', letterSpacing:'-0.02em' }}>Machines</h1>
          <p style={{ color:'var(--text-muted)', fontSize:'12px', marginTop:'2px' }}>{machines.length} registered</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={fetchMachines}>[ refresh ]</button>
      </div>

      <div style={{ display:'flex', gap:'10px', marginBottom:'16px', flexWrap:'wrap' }}>
        <input className="input" type="text" placeholder="search hostname, mac, ip..." value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth:'280px' }} />
        <select className="input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ maxWidth:'150px' }}>
          <option value="">all statuses</option>
          <option value="online">online</option>
          <option value="idle">idle</option>
          <option value="offline">offline</option>
        </select>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom:'14px', fontSize:'12px' }}>{error}</div>}

      {loading ? (
        <div style={{ display:'flex', justifyContent:'center', padding:'60px' }}><div className="spinner" /></div>
      ) : sorted.length === 0 ? (
        <div className="card" style={{ textAlign:'center', padding:'50px', color:'var(--text-muted)', fontSize:'13px' }}>
          <div style={{ marginBottom:'8px', fontSize:'24px' }}>_</div>
          no machines found — run an agent to register one
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th onClick={() => handleSort('hostname')} style={{ cursor:'pointer' }}>hostname<SortIcon k="hostname" /></th>
                <th>status</th>
                <th>os</th>
                <th>ip</th>
                <th onClick={() => handleSort('last_seen')} style={{ cursor:'pointer' }}>last seen<SortIcon k="last_seen" /></th>
                <th onClick={() => handleSort('total_idle_seconds')} style={{ cursor:'pointer' }}>idle<SortIcon k="total_idle_seconds" /></th>
                <th onClick={() => handleSort('energy_wasted_kwh')} style={{ cursor:'pointer' }}>energy<SortIcon k="energy_wasted_kwh" /></th>
                <th onClick={() => handleSort('energy_cost_usd')} style={{ cursor:'pointer' }}>cost<SortIcon k="energy_cost_usd" /></th>
                <th>actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(m => (
                <tr key={m.id}>
                  <td>
                    <Link to={`/machines/${m.id}`} style={{ color:'var(--text-primary)', fontWeight:'500', textDecoration:'none', transition:'color var(--transition)' }}
                      onMouseEnter={e => e.target.style.color='var(--cyan)'}
                      onMouseLeave={e => e.target.style.color='var(--text-primary)'}
                    >{m.hostname}</Link>
                    <div style={{ fontSize:'10px', color:'var(--text-muted)', marginTop:'1px', fontFamily:'monospace' }}>{m.mac_address}</div>
                  </td>
                  <td><StatusBadge status={m.status} /></td>
                  <td>
                    <div style={{ fontSize:'12px' }}>{m.os_type}</div>
                    {m.os_version && <div style={{ fontSize:'10px', color:'var(--text-muted)', marginTop:'1px' }}>{m.os_version.substring(0,40)}</div>}
                  </td>
                  <td style={{ fontFamily:'monospace', fontSize:'12px' }}>{m.ip_address || '—'}</td>
                  <td style={{ fontSize:'12px' }}>{m.last_seen ? new Date(m.last_seen).toLocaleString() : '—'}</td>
                  <td style={{ fontSize:'12px' }}>{fmtIdle(m.total_idle_seconds)}</td>
                  <td><span style={{ color:'var(--cyan)', fontWeight:'600', fontSize:'12px' }}>{m.energy_wasted_kwh.toFixed(3)} kWh</span></td>
                  <td><span style={{ color:'var(--amber-primary)', fontWeight:'600', fontSize:'12px' }}>${m.energy_cost_usd.toFixed(2)}</span></td>
                  <td>
                    <div style={{ display:'flex', gap:'5px' }}>
                      <Link to={`/machines/${m.id}`} className="btn btn-secondary btn-sm">view</Link>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(m.id, m.hostname)} disabled={deleting === m.id}>
                        {deleting === m.id ? '...' : 'del'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
