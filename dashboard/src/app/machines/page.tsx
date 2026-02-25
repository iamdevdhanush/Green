'use client';
import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { machinesAPI } from '@/lib/api';
import ProtectedLayout from '@/components/ProtectedLayout';

interface Machine {
  id: number;
  hostname: string;
  mac_address: string;
  os_type: string;
  os_version?: string;
  ip_address?: string;
  status: 'online' | 'idle' | 'offline';
  last_seen: string;
  total_idle_seconds: number;
  energy_wasted_kwh: number;
  energy_cost_usd: number;
}

function StatusDot({ status }: { status: string }) {
  const map: Record<string, { color: string; label: string }> = {
    online: { color: 'var(--green)', label: 'online' },
    idle: { color: 'var(--amber)', label: 'idle' },
    offline: { color: 'var(--text-muted)', label: 'offline' },
  };
  const s = map[status] || map.offline;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: s.color }}>
      <span style={{
        width: '7px', height: '7px', borderRadius: '50%', background: s.color, flexShrink: 0,
        animation: status === 'online' ? 'pulse 2s infinite' : undefined,
        boxShadow: status === 'online' ? `0 0 4px ${s.color}` : undefined,
      }} />
      {s.label}
    </span>
  );
}

function formatIdle(sec: number) {
  if (!sec) return '—';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function MachinesContent() {
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [deleting, setDeleting] = useState<number | null>(null);

  const fetchMachines = useCallback(async () => {
    try {
      const params: Record<string, unknown> = { limit: 500 };
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;
      const { data } = await machinesAPI.list(params);
      setMachines(data);
      setError('');
    } catch {
      setError('Failed to load machines.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, search]);

  useEffect(() => {
    fetchMachines();
    const iv = setInterval(fetchMachines, 30000);
    return () => clearInterval(iv);
  }, [fetchMachines]);

  const handleDelete = async (id: number, hostname: string) => {
    if (!confirm(`Delete "${hostname}"? This removes all history.`)) return;
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

  return (
    <div className="animate-in">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '4px' }}>
            // greenops / machines
          </div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            Machine Registry<span className="cursor" />
          </h1>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {machines.length} registered endpoint{machines.length !== 1 ? 's' : ''}
          </div>
        </div>
        <button
          onClick={fetchMachines}
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

      {/* Filters */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
        <input
          type="text"
          placeholder="search hostname, mac, ip..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            padding: '8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', color: 'var(--text-primary)', fontFamily: 'var(--font)',
            fontSize: '12px', outline: 'none', width: '280px', transition: 'border-color var(--transition)',
          }}
          onFocus={e => { e.target.style.borderColor = 'var(--accent)'; }}
          onBlur={e => { e.target.style.borderColor = 'var(--border)'; }}
        />
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{
            padding: '8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', color: 'var(--text-secondary)', fontFamily: 'var(--font)',
            fontSize: '12px', outline: 'none', cursor: 'pointer',
          }}
        >
          <option value="">all status</option>
          <option value="online">online</option>
          <option value="idle">idle</option>
          <option value="offline">offline</option>
        </select>
      </div>

      {error && (
        <div style={{
          background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)',
          color: 'var(--red)', padding: '10px 14px', borderRadius: 'var(--radius)',
          fontSize: '12px', marginBottom: '14px',
        }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
          <div className="spinner" />
        </div>
      ) : machines.length === 0 ? (
        <div style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border)',
          padding: '60px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px',
        }}>
          <div style={{ marginBottom: '8px', fontSize: '20px' }}>[]</div>
          no machines registered — deploy an agent to get started
        </div>
      ) : (
        <div style={{ border: '1px solid var(--border)', overflow: 'hidden' }}>
          {/* Table header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 90px 80px 120px 140px 100px 90px 100px',
            background: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border)',
            padding: '10px 14px',
          }}>
            {['hostname', 'status', 'os', 'ip address', 'last seen', 'idle time', 'energy', 'actions'].map(h => (
              <span key={h} style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                {h}
              </span>
            ))}
          </div>

          {machines.map((m, i) => (
            <div
              key={m.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 90px 80px 120px 140px 100px 90px 100px',
                padding: '12px 14px',
                borderBottom: i < machines.length - 1 ? '1px solid var(--border)' : 'none',
                transition: 'background var(--transition)',
                alignItems: 'center',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
            >
              <div>
                <Link
                  href={`/machines/${m.id}`}
                  style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: '500', textDecoration: 'none' }}
                  onMouseEnter={e => { (e.target as HTMLElement).style.color = 'var(--accent)'; }}
                  onMouseLeave={e => { (e.target as HTMLElement).style.color = 'var(--text-primary)'; }}
                >
                  {m.hostname}
                </Link>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font)', marginTop: '1px' }}>
                  {m.mac_address}
                </div>
              </div>
              <div><StatusDot status={m.status} /></div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{m.os_type}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font)' }}>{m.ip_address || '—'}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {m.last_seen ? new Date(m.last_seen).toLocaleString() : '—'}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{formatIdle(m.total_idle_seconds)}</div>
              <div style={{ fontSize: '12px', color: 'var(--accent)', fontWeight: '600' }}>
                {m.energy_wasted_kwh.toFixed(3)} kWh
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <Link
                  href={`/machines/${m.id}`}
                  style={{
                    padding: '4px 10px', background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)', color: 'var(--text-secondary)', fontSize: '11px',
                    textDecoration: 'none', transition: 'all var(--transition)',
                  }}
                >
                  view
                </Link>
                <button
                  onClick={() => handleDelete(m.id, m.hostname)}
                  disabled={deleting === m.id}
                  style={{
                    padding: '4px 8px', background: 'transparent', border: '1px solid transparent',
                    borderRadius: 'var(--radius)', color: 'var(--text-muted)', fontSize: '11px',
                    cursor: 'pointer', fontFamily: 'var(--font)', transition: 'all var(--transition)',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.color = 'var(--red)'; e.currentTarget.style.borderColor = 'rgba(239,68,68,0.2)'; }}
                  onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'transparent'; }}
                >
                  {deleting === m.id ? '...' : 'del'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function MachinesPage() {
  return (
    <ProtectedLayout>
      <MachinesContent />
    </ProtectedLayout>
  );
}
