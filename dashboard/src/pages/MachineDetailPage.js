import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { machinesAPI } from '../api/client';

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status}</span>;
}

function InfoRow({ label, value, mono = false }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: '500' }}>{label}</span>
      <span style={{ fontSize: '13px', color: 'var(--text-primary)', fontFamily: mono ? 'monospace' : undefined, textAlign: 'right', maxWidth: '60%', wordBreak: 'break-all' }}>
        {value || '—'}
      </span>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '10px 14px', fontSize: '12px' }}>
      <p style={{ color: 'var(--text-muted)', marginBottom: '6px' }}>{new Date(label).toLocaleTimeString()}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>{p.name}: {p.value?.toFixed ? p.value.toFixed(1) : p.value}</p>
      ))}
    </div>
  );
}

export default function MachineDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [machine, setMachine] = useState(null);
  const [heartbeats, setHeartbeats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesMode, setNotesMode] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [mRes, hRes] = await Promise.all([
          machinesAPI.get(id),
          machinesAPI.heartbeats(id, { limit: 50 }),
        ]);
        setMachine(mRes.data);
        setEditNotes(mRes.data.notes || '');
        setHeartbeats(hRes.data.reverse()); // oldest first for chart
        setError('');
      } catch (err) {
        if (err.response?.status === 404) {
          setError('Machine not found.');
        } else {
          setError('Failed to load machine details.');
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    try {
      await machinesAPI.update(id, { notes: editNotes });
      setMachine(prev => ({ ...prev, notes: editNotes }));
      setNotesMode(false);
    } catch {
      setError('Failed to save notes.');
    } finally {
      setSavingNotes(false);
    }
  };

  const handleRevokeToken = async () => {
    if (!window.confirm('Revoke this machine\'s agent token? The agent will need to re-register.')) return;
    try {
      await machinesAPI.revokeToken(id);
      setError('');
      alert('Token revoked. The agent will need to re-register.');
    } catch {
      setError('Failed to revoke token.');
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '80px' }}>
        <div className="spinner" />
      </div>
    );
  }

  if (error && !machine) {
    return (
      <div style={{ maxWidth: '500px', margin: '80px auto', textAlign: 'center' }}>
        <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>
        <Link to="/machines" className="btn btn-secondary">← Back to Machines</Link>
      </div>
    );
  }

  const idleHours = machine ? (machine.total_idle_seconds / 3600).toFixed(1) : 0;
  const totalTime = machine ? machine.total_idle_seconds + machine.total_active_seconds : 0;
  const idlePct = totalTime > 0 ? ((machine.total_idle_seconds / totalTime) * 100).toFixed(1) : 0;

  // Chart data
  const chartData = heartbeats.map(h => ({
    time: h.timestamp,
    idle: h.idle_seconds,
    cpu: h.cpu_usage,
    memory: h.memory_usage,
  }));

  return (
    <div className="animate-in">
      {/* Back nav */}
      <div style={{ marginBottom: '20px' }}>
        <Link to="/machines" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', textDecoration: 'none', fontSize: '14px' }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
          onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
        >
          ← Back to Machines
        </Link>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
            <h1 style={{ fontSize: '22px', fontWeight: '700', letterSpacing: '-0.02em' }}>{machine?.hostname}</h1>
            <StatusBadge status={machine?.status} />
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', fontFamily: 'monospace' }}>{machine?.mac_address}</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary btn-sm" onClick={handleRevokeToken}>
            Revoke Token
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '20px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
            {[
              { label: 'Idle Time', value: `${idleHours}h`, sub: `${idlePct}% of total`, color: 'var(--amber-primary)' },
              { label: 'Energy Wasted', value: `${machine?.energy_wasted_kwh?.toFixed(3)} kWh`, sub: 'Cumulative', color: 'var(--green-primary)' },
              { label: 'Est. Cost', value: `$${machine?.energy_cost_usd?.toFixed(2)}`, sub: 'Electricity waste', color: 'var(--red-primary)' },
            ].map(s => (
              <div key={s.label} className="card" style={{ padding: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>{s.label}</div>
                <div style={{ fontSize: '22px', fontWeight: '700', color: s.color, letterSpacing: '-0.02em' }}>{s.value}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '3px' }}>{s.sub}</div>
              </div>
            ))}
          </div>

          {/* Heartbeat Chart */}
          <div className="card">
            <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '4px' }}>Recent Heartbeats</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>Last {heartbeats.length} heartbeats</p>
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false}
                    tickFormatter={v => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} width={36} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '12px' }} />
                  <Line type="monotone" dataKey="idle" name="Idle (sec)" stroke="#f59e0b" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="cpu" name="CPU %" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="memory" name="Memory %" stroke="#8b5cf6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '160px', color: 'var(--text-muted)', fontSize: '14px' }}>
                Not enough data to display chart
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '600' }}>Notes</h3>
              {notesMode ? (
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => { setNotesMode(false); setEditNotes(machine?.notes || ''); }}>Cancel</button>
                  <button className="btn btn-primary btn-sm" onClick={handleSaveNotes} disabled={savingNotes}>{savingNotes ? 'Saving...' : 'Save'}</button>
                </div>
              ) : (
                <button className="btn btn-secondary btn-sm" onClick={() => setNotesMode(true)}>Edit</button>
              )}
            </div>
            {notesMode ? (
              <textarea
                className="input"
                value={editNotes}
                onChange={e => setEditNotes(e.target.value)}
                placeholder="Add notes about this machine..."
                style={{ minHeight: '80px', resize: 'vertical' }}
              />
            ) : (
              <p style={{ fontSize: '14px', color: machine?.notes ? 'var(--text-secondary)' : 'var(--text-muted)', fontStyle: machine?.notes ? 'normal' : 'italic' }}>
                {machine?.notes || 'No notes added.'}
              </p>
            )}
          </div>
        </div>

        {/* Info panel */}
        <div className="card" style={{ padding: '20px', alignSelf: 'flex-start' }}>
          <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px' }}>Machine Details</h3>
          <InfoRow label="Hostname" value={machine?.hostname} />
          <InfoRow label="MAC Address" value={machine?.mac_address} mono />
          <InfoRow label="IP Address" value={machine?.ip_address} mono />
          <InfoRow label="OS Type" value={machine?.os_type} />
          <InfoRow label="OS Version" value={machine?.os_version} />
          <InfoRow label="Agent Version" value={machine?.agent_version} />
          <InfoRow label="Status" value={<StatusBadge status={machine?.status} />} />
          <InfoRow label="First Seen" value={machine?.first_seen ? new Date(machine.first_seen).toLocaleString() : null} />
          <InfoRow label="Last Seen" value={machine?.last_seen ? new Date(machine.last_seen).toLocaleString() : null} />
          <InfoRow label="Active Time" value={machine ? `${(machine.total_active_seconds / 3600).toFixed(1)}h` : null} />
          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Machine ID
            </div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', color: 'var(--text-muted)' }}>#{machine?.id}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
