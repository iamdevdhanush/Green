import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { machinesAPI } from '../api/client';

function StatusBadge({ status }) {
  const cls = `badge badge-${status}`;
  return <span className={cls}>{status}</span>;
}

function formatIdleTime(seconds) {
  if (!seconds) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
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
    } catch (err) {
      setError('Failed to load machines.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, search]);

  useEffect(() => {
    fetchMachines();
    const interval = setInterval(fetchMachines, 30000);
    return () => clearInterval(interval);
  }, [fetchMachines]);

  const handleDelete = async (id, hostname) => {
    if (!window.confirm(`Delete machine "${hostname}"? This will remove all heartbeat history.`)) return;
    setDeleting(id);
    try {
      await machinesAPI.delete(id);
      setMachines(prev => prev.filter(m => m.id !== id));
    } catch {
      setError('Failed to delete machine.');
    } finally {
      setDeleting(null);
    }
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

  const SortIcon = ({ k }) => (
    <span style={{ marginLeft: '4px', opacity: sortKey === k ? 1 : 0.3 }}>
      {sortKey === k ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
    </span>
  );

  return (
    <div className="animate-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', letterSpacing: '-0.03em' }}>Machines</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>
            {machines.length} registered machine{machines.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={fetchMachines}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <input
          className="input"
          type="text"
          placeholder="Search by hostname, MAC, IP..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ maxWidth: '320px' }}
        />
        <select
          className="input"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{ maxWidth: '160px' }}
        >
          <option value="">All statuses</option>
          <option value="online">Online</option>
          <option value="idle">Idle</option>
          <option value="offline">Offline</option>
        </select>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
          <div className="spinner" />
        </div>
      ) : sorted.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ margin: '0 auto 12px', opacity: 0.5 }}>
            <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
          </svg>
          <p style={{ fontWeight: '500', marginBottom: '4px' }}>No machines found</p>
          <p style={{ fontSize: '13px' }}>Run an agent on a machine to register it here.</p>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th onClick={() => handleSort('hostname')} style={{ cursor: 'pointer' }}>
                  Hostname <SortIcon k="hostname" />
                </th>
                <th>Status</th>
                <th>OS</th>
                <th>IP Address</th>
                <th onClick={() => handleSort('last_seen')} style={{ cursor: 'pointer' }}>
                  Last Seen <SortIcon k="last_seen" />
                </th>
                <th onClick={() => handleSort('total_idle_seconds')} style={{ cursor: 'pointer' }}>
                  Idle Time <SortIcon k="total_idle_seconds" />
                </th>
                <th onClick={() => handleSort('energy_wasted_kwh')} style={{ cursor: 'pointer' }}>
                  Energy <SortIcon k="energy_wasted_kwh" />
                </th>
                <th onClick={() => handleSort('energy_cost_usd')} style={{ cursor: 'pointer' }}>
                  Cost <SortIcon k="energy_cost_usd" />
                </th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(machine => (
                <tr key={machine.id}>
                  <td>
                    <Link
                      to={`/machines/${machine.id}`}
                      style={{ color: 'var(--text-primary)', fontWeight: '500', textDecoration: 'none' }}
                      onMouseEnter={e => e.target.style.color = 'var(--green-primary)'}
                      onMouseLeave={e => e.target.style.color = 'var(--text-primary)'}
                    >
                      {machine.hostname}
                    </Link>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'monospace' }}>
                      {machine.mac_address}
                    </div>
                  </td>
                  <td><StatusBadge status={machine.status} /></td>
                  <td>
                    <div style={{ fontSize: '13px' }}>{machine.os_type}</div>
                    {machine.os_version && (
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '1px' }}>
                        {machine.os_version.substring(0, 40)}
                      </div>
                    )}
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: '13px' }}>
                    {machine.ip_address || '—'}
                  </td>
                  <td style={{ fontSize: '13px' }}>
                    {machine.last_seen ? new Date(machine.last_seen).toLocaleString() : '—'}
                  </td>
                  <td style={{ fontSize: '13px' }}>
                    {formatIdleTime(machine.total_idle_seconds)}
                  </td>
                  <td>
                    <span style={{ color: 'var(--green-primary)', fontWeight: '600', fontSize: '13px' }}>
                      {machine.energy_wasted_kwh.toFixed(3)} kWh
                    </span>
                  </td>
                  <td>
                    <span style={{ color: 'var(--amber-primary)', fontWeight: '600', fontSize: '13px' }}>
                      ${machine.energy_cost_usd.toFixed(2)}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <Link to={`/machines/${machine.id}`} className="btn btn-secondary btn-sm">
                        View
                      </Link>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(machine.id, machine.hostname)}
                        disabled={deleting === machine.id}
                      >
                        {deleting === machine.id ? '...' : 'Delete'}
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
