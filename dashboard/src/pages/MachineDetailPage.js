import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { machinesAPI } from '../api/client';

function InfoRow({ label, value, mono = false }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', padding:'9px 0', borderBottom:'1px solid var(--border)' }}>
      <span style={{ fontSize:'11px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em' }}>{label}</span>
      <span style={{ fontSize:'12px', color:'var(--text-primary)', fontFamily: mono ? 'monospace' : undefined, textAlign:'right', maxWidth:'60%', wordBreak:'break-all' }}>{value || '—'}</span>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:'var(--bg-tertiary)', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', padding:'8px 12px', fontSize:'11px' }}>
      <p style={{ color:'var(--text-muted)', marginBottom:'4px' }}>{new Date(label).toLocaleTimeString()}</p>
      {payload.map((p, i) => <p key={i} style={{ color:p.color }}>{p.name}: {p.value?.toFixed ? p.value.toFixed(1) : p.value}</p>)}
    </div>
  );
}

export default function MachineDetailPage() {
  const { id } = useParams();
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
        const [mRes, hRes] = await Promise.all([machinesAPI.get(id), machinesAPI.heartbeats(id, { limit:50 })]);
        setMachine(mRes.data);
        setEditNotes(mRes.data.notes || '');
        setHeartbeats([...hRes.data].reverse());
        setError('');
      } catch (err) {
        setError(err.response?.status === 404 ? 'Machine not found.' : 'Failed to load machine.');
      } finally { setLoading(false); }
    }
    load();
  }, [id]);

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    try {
      await machinesAPI.update(id, { notes: editNotes });
      setMachine(prev => ({ ...prev, notes: editNotes }));
      setNotesMode(false);
    } catch { setError('Failed to save notes.'); }
    finally { setSavingNotes(false); }
  };

  const handleRevokeToken = async () => {
    if (!window.confirm('Revoke agent token? The agent must re-register.')) return;
    try {
      await machinesAPI.revokeToken(id);
      alert('Token revoked. Agent must re-register.');
    } catch { setError('Failed to revoke token.'); }
  };

  if (loading) return <div style={{ display:'flex', justifyContent:'center', padding:'80px' }}><div className="spinner" /></div>;
  if (error && !machine) return (
    <div style={{ maxWidth:'400px', margin:'80px auto', textAlign:'center' }}>
      <div className="alert alert-error" style={{ marginBottom:'16px' }}>{error}</div>
      <Link to="/machines" className="btn btn-secondary">← back</Link>
    </div>
  );

  const idleHours = machine ? (machine.total_idle_seconds / 3600).toFixed(1) : 0;
  const totalTime = machine ? machine.total_idle_seconds + machine.total_active_seconds : 0;
  const idlePct = totalTime > 0 ? ((machine.total_idle_seconds / totalTime) * 100).toFixed(1) : 0;
  const chartData = heartbeats.map(h => ({ time: h.timestamp, idle: h.idle_seconds, cpu: h.cpu_usage, memory: h.memory_usage }));

  return (
    <div className="animate-in">
      <div style={{ marginBottom:'16px' }}>
        <Link to="/machines" style={{ color:'var(--text-muted)', textDecoration:'none', fontSize:'12px', transition:'color var(--transition)' }}
          onMouseEnter={e => e.target.style.color='var(--cyan)'}
          onMouseLeave={e => e.target.style.color='var(--text-muted)'}
        >← /machines</Link>
      </div>

      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:'20px', flexWrap:'wrap', gap:'10px' }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:'10px', marginBottom:'4px' }}>
            <h1 style={{ fontSize:'20px', fontWeight:'700', letterSpacing:'-0.02em' }}>{machine?.hostname}</h1>
            <span className={`badge badge-${machine?.status}`}>{machine?.status}</span>
          </div>
          <p style={{ color:'var(--text-muted)', fontSize:'11px', fontFamily:'monospace' }}>{machine?.mac_address}</p>
        </div>
        <button className="btn btn-danger btn-sm" onClick={handleRevokeToken}>revoke token</button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom:'14px', fontSize:'12px' }}>{error}</div>}

      <div style={{ display:'grid', gridTemplateColumns:'1fr 300px', gap:'16px' }}>
        <div style={{ display:'flex', flexDirection:'column', gap:'16px' }}>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'12px' }}>
            {[
              { label:'idle time', value:`${idleHours}h`, sub:`${idlePct}% of total`, color:'var(--amber-primary)' },
              { label:'energy wasted', value:`${machine?.energy_wasted_kwh?.toFixed(3)} kWh`, sub:'cumulative', color:'var(--cyan)' },
              { label:'est. cost', value:`$${machine?.energy_cost_usd?.toFixed(2)}`, sub:'electricity waste', color:'var(--red-primary)' },
            ].map(s => (
              <div key={s.label} className="card" style={{ padding:'14px', borderLeft:`2px solid ${s.color}` }}>
                <div style={{ fontSize:'10px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'4px' }}>{s.label}</div>
                <div style={{ fontSize:'20px', fontWeight:'700', color:s.color }}>{s.value}</div>
                <div style={{ fontSize:'11px', color:'var(--text-muted)', marginTop:'2px' }}>{s.sub}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <div style={{ fontSize:'10px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'4px' }}>recent heartbeats</div>
            <div style={{ fontSize:'13px', fontWeight:'600', color:'var(--text-primary)', marginBottom:'16px' }}>Last {heartbeats.length} readings</div>
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData} margin={{ top:4, right:0, bottom:0, left:0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize:10, fill:'var(--text-muted)', fontFamily:'var(--font)' }} tickLine={false} axisLine={false}
                    tickFormatter={v => new Date(v).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })} />
                  <YAxis tick={{ fontSize:10, fill:'var(--text-muted)', fontFamily:'var(--font)' }} tickLine={false} axisLine={false} width={32} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize:'11px', paddingTop:'10px', fontFamily:'var(--font)' }} />
                  <Line type="monotone" dataKey="idle" name="Idle (sec)" stroke="var(--amber-primary)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="cpu" name="CPU %" stroke="var(--cyan)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="memory" name="Mem %" stroke="var(--blue-primary)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'140px', color:'var(--text-muted)', fontSize:'12px' }}>not enough data</div>
            )}
          </div>

          <div className="card">
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'12px' }}>
              <div style={{ fontSize:'13px', fontWeight:'600', color:'var(--text-primary)' }}>Notes</div>
              {notesMode ? (
                <div style={{ display:'flex', gap:'6px' }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => { setNotesMode(false); setEditNotes(machine?.notes || ''); }}>cancel</button>
                  <button className="btn btn-primary btn-sm" onClick={handleSaveNotes} disabled={savingNotes}>{savingNotes ? '...' : 'save'}</button>
                </div>
              ) : (
                <button className="btn btn-secondary btn-sm" onClick={() => setNotesMode(true)}>edit</button>
              )}
            </div>
            {notesMode ? (
              <textarea className="input" value={editNotes} onChange={e => setEditNotes(e.target.value)} placeholder="Add notes..." style={{ minHeight:'70px', resize:'vertical' }} />
            ) : (
              <p style={{ fontSize:'13px', color: machine?.notes ? 'var(--text-secondary)' : 'var(--text-muted)', fontStyle: machine?.notes ? 'normal' : 'italic' }}>
                {machine?.notes || 'No notes added.'}
              </p>
            )}
          </div>
        </div>

        <div className="card" style={{ padding:'18px', alignSelf:'flex-start' }}>
          <div style={{ fontSize:'10px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'14px' }}>machine details</div>
          <InfoRow label="hostname" value={machine?.hostname} />
          <InfoRow label="mac" value={machine?.mac_address} mono />
          <InfoRow label="ip" value={machine?.ip_address} mono />
          <InfoRow label="os type" value={machine?.os_type} />
          <InfoRow label="os version" value={machine?.os_version} />
          <InfoRow label="agent ver" value={machine?.agent_version} />
          <InfoRow label="first seen" value={machine?.first_seen ? new Date(machine.first_seen).toLocaleString() : null} />
          <InfoRow label="last seen" value={machine?.last_seen ? new Date(machine.last_seen).toLocaleString() : null} />
          <InfoRow label="active time" value={machine ? `${(machine.total_active_seconds/3600).toFixed(1)}h` : null} />
          <div style={{ marginTop:'14px', paddingTop:'14px', borderTop:'1px solid var(--border)' }}>
            <div style={{ fontSize:'10px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:'4px' }}>machine id</div>
            <div style={{ fontFamily:'monospace', fontSize:'12px', color:'var(--text-muted)' }}>#{machine?.id}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
