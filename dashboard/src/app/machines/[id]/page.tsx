'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { machinesAPI } from '@/lib/api';
import ProtectedLayout from '@/components/ProtectedLayout';

interface Machine {
  id: number; hostname: string; mac_address: string; os_type: string;
  os_version?: string; ip_address?: string; status: string;
  first_seen: string; last_seen: string;
  total_idle_seconds: number; total_active_seconds: number;
  energy_wasted_kwh: number; energy_cost_usd: number;
  agent_version?: string; notes?: string;
}

interface Heartbeat {
  id: number; timestamp: string; idle_seconds: number;
  cpu_usage?: number; memory_usage?: number; is_idle: boolean; energy_delta_kwh: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
      padding: '10px 14px', fontSize: '11px', borderRadius: 'var(--radius)',
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>
        {new Date(label).toLocaleTimeString()}
      </div>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ color: p.color }}>{p.name}: {p.value?.toFixed ? p.value.toFixed(1) : p.value}</div>
      ))}
    </div>
  );
};

function InfoRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>{label}</span>
      <span style={{ fontSize: '12px', color: 'var(--text-primary)', fontFamily: mono ? 'var(--font)' : undefined, textAlign: 'right', maxWidth: '60%', wordBreak: 'break-all' }}>
        {value || '—'}
      </span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { c: string; bg: string }> = {
    online: { c: 'var(--green)', bg: 'var(--green-dim)' },
    idle: { c: 'var(--amber)', bg: 'var(--amber-dim)' },
    offline: { c: 'var(--text-muted)', bg: 'var(--muted-dim)' },
  };
  const s = map[status] || map.offline;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '6px',
      padding: '3px 10px', background: s.bg, borderRadius: 'var(--radius)',
      color: s.c, fontSize: '11px', letterSpacing: '0.06em', textTransform: 'uppercase',
    }}>
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: s.c, animation: status === 'online' ? 'pulse 2s infinite' : undefined }} />
      {status}
    </span>
  );
}

function MachineDetailContent() {
  const params = useParams();
  const id = Number(params.id);
  const [machine, setMachine] = useState<Machine | null>(null);
  const [heartbeats, setHeartbeats] = useState<Heartbeat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState('');
  const [notesEdit, setNotesEdit] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [mRes, hRes] = await Promise.all([
          machinesAPI.get(id),
          machinesAPI.heartbeats(id, { limit: 50 }),
        ]);
        setMachine(mRes.data);
        setNotes(mRes.data.notes || '');
        setHeartbeats([...hRes.data].reverse());
      } catch (e: any) {
        setError(e.response?.status === 404 ? 'Machine not found.' : 'Failed to load machine.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const saveNotes = async () => {
    setSaving(true);
    try {
      await machinesAPI.update(id, { notes });
      setMachine(prev => prev ? { ...prev, notes } : prev);
      setNotesEdit(false);
    } catch {
      setError('Failed to save notes.');
    } finally {
      setSaving(false);
    }
  };

  const revokeToken = async () => {
    if (!confirm('Revoke agent token? The agent will need to re-register.')) return;
    try {
      await machinesAPI.revokeToken(id);
      alert('Token revoked.');
    } catch {
      setError('Failed to revoke token.');
    }
  };

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '80px' }}><div className="spinner" /></div>;
  if (error && !machine) return (
    <div style={{ textAlign: 'center', padding: '80px' }}>
      <div style={{ color: 'var(--red)', marginBottom: '16px', fontSize: '13px' }}>{error}</div>
      <Link href="/machines" style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: '12px' }}>← back to machines</Link>
    </div>
  );

  const idleHours = ((machine?.total_idle_seconds || 0) / 3600).toFixed(1);
  const totalSec = (machine?.total_idle_seconds || 0) + (machine?.total_active_seconds || 0);
  const idlePct = totalSec > 0 ? (((machine?.total_idle_seconds || 0) / totalSec) * 100).toFixed(1) : '0';

  const chartData = heartbeats.map(h => ({
    time: h.timestamp,
    idle: h.idle_seconds,
    cpu: h.cpu_usage,
    mem: h.memory_usage,
  }));

  return (
    <div className="animate-in">
      {/* Back */}
      <Link href="/machines" style={{ fontSize: '12px', color: 'var(--text-muted)', textDecoration: 'none', display: 'inline-block', marginBottom: '16px' }}
        onMouseEnter={e => { (e.target as HTMLElement).style.color = 'var(--accent)'; }}
        onMouseLeave={e => { (e.target as HTMLElement).style.color = 'var(--text-muted)'; }}
      >
        ← /machines
      </Link>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '4px' }}>
            // greenops / machines / {machine?.id}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h1 style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
              {machine?.hostname}
            </h1>
            <StatusBadge status={machine?.status || 'offline'} />
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font)', marginTop: '4px' }}>
            {machine?.mac_address}
          </div>
        </div>
        <button onClick={revokeToken} style={{
          padding: '7px 14px', background: 'transparent', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', color: 'var(--text-muted)', fontFamily: 'var(--font)',
          fontSize: '12px', cursor: 'pointer', transition: 'all var(--transition)',
        }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(239,68,68,0.3)'; e.currentTarget.style.color = 'var(--red)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
        >
          revoke token
        </button>
      </div>

      {error && <div style={{ color: 'var(--red)', fontSize: '12px', marginBottom: '14px' }}>{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {[
              { label: 'idle time', value: `${idleHours}h`, sub: `${idlePct}% of total`, color: 'var(--amber)' },
              { label: 'energy wasted', value: `${machine?.energy_wasted_kwh?.toFixed(3)} kWh`, sub: 'cumulative', color: 'var(--accent)' },
              { label: 'est. cost', value: `$${machine?.energy_cost_usd?.toFixed(2)}`, sub: 'electricity', color: 'var(--red)' },
            ].map(s => (
              <div key={s.label} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '16px' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>{s.label}</div>
                <div style={{ fontSize: '20px', fontWeight: '700', color: s.color, letterSpacing: '-0.02em' }}>{s.value}</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '3px' }}>{s.sub}</div>
              </div>
            ))}
          </div>

          {/* Chart */}
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '20px' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '2px' }}>// heartbeat_log</div>
            <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px' }}>
              Recent Heartbeats ({heartbeats.length})
            </div>
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 9, fill: 'var(--text-muted)', fontFamily: 'var(--font)' }} tickLine={false} axisLine={false}
                    tickFormatter={v => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--text-muted)', fontFamily: 'var(--font)' }} tickLine={false} axisLine={false} width={32} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'var(--font)' }} />
                  <Line type="monotone" dataKey="idle" name="idle(s)" stroke="var(--amber)" strokeWidth={1.5} dot={false} />
                  <Line type="monotone" dataKey="cpu" name="cpu%" stroke="var(--accent)" strokeWidth={1.5} dot={false} />
                  <Line type="monotone" dataKey="mem" name="mem%" stroke="var(--green)" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: '160px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                insufficient data
              </div>
            )}
          </div>

          {/* Notes */}
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>// notes</div>
              {notesEdit ? (
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button onClick={() => { setNotesEdit(false); setNotes(machine?.notes || ''); }}
                    style={{ padding: '5px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-muted)', fontFamily: 'var(--font)', fontSize: '11px', cursor: 'pointer' }}>
                    cancel
                  </button>
                  <button onClick={saveNotes} disabled={saving}
                    style={{ padding: '5px 12px', background: 'var(--accent-dim)', border: '1px solid var(--accent-border)', borderRadius: 'var(--radius)', color: 'var(--accent)', fontFamily: 'var(--font)', fontSize: '11px', cursor: 'pointer' }}>
                    {saving ? 'saving...' : 'save'}
                  </button>
                </div>
              ) : (
                <button onClick={() => setNotesEdit(true)}
                  style={{ padding: '5px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius)', color: 'var(--text-muted)', fontFamily: 'var(--font)', fontSize: '11px', cursor: 'pointer' }}>
                  edit
                </button>
              )}
            </div>
            {notesEdit ? (
              <textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="add notes..."
                style={{
                  width: '100%', minHeight: '80px', padding: '10px 12px',
                  background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)', color: 'var(--text-primary)',
                  fontFamily: 'var(--font)', fontSize: '13px', outline: 'none', resize: 'vertical',
                }}
              />
            ) : (
              <p style={{ fontSize: '13px', color: machine?.notes ? 'var(--text-secondary)' : 'var(--text-muted)', fontStyle: machine?.notes ? 'normal' : 'italic' }}>
                {machine?.notes || 'no notes.'}
              </p>
            )}
          </div>
        </div>

        {/* Info panel */}
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '18px', alignSelf: 'flex-start' }}>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '12px' }}>
            // machine.info
          </div>
          <InfoRow label="hostname" value={machine?.hostname} />
          <InfoRow label="mac_address" value={machine?.mac_address} mono />
          <InfoRow label="ip_address" value={machine?.ip_address} mono />
          <InfoRow label="os_type" value={machine?.os_type} />
          <InfoRow label="os_version" value={machine?.os_version} />
          <InfoRow label="agent_ver" value={machine?.agent_version} />
          <InfoRow label="status" value={<StatusBadge status={machine?.status || 'offline'} />} />
          <InfoRow label="first_seen" value={machine?.first_seen ? new Date(machine.first_seen).toLocaleDateString() : undefined} />
          <InfoRow label="last_seen" value={machine?.last_seen ? new Date(machine.last_seen).toLocaleString() : undefined} />
          <InfoRow label="active_time" value={machine ? `${(machine.total_active_seconds / 3600).toFixed(1)}h` : undefined} />
          <div style={{ marginTop: '14px', paddingTop: '14px', borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '4px' }}>machine_id</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font)' }}>#{machine?.id}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MachineDetailPage() {
  return (
    <ProtectedLayout>
      <MachineDetailContent />
    </ProtectedLayout>
  );
}
