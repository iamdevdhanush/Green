import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setError('');
    setLoading(true);
    try {
      await login(username.trim(), password);
      navigate('/');
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object') setError(detail.message || 'Login failed.');
      else if (typeof detail === 'string') setError(detail);
      else if (err.response?.status === 429) setError('Too many login attempts. Please wait.');
      else setError('Invalid username or password.');
    } finally { setLoading(false); }
  };

  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--bg-primary)', padding:'24px' }}>
      <div style={{ width:'100%', maxWidth:'380px' }} className="animate-in">
        <div style={{ marginBottom:'28px' }}>
          <div style={{ fontSize:'22px', fontWeight:'700', color:'var(--cyan)', letterSpacing:'0.05em', marginBottom:'4px' }}>
            GREENOPS<span className="cursor" />
          </div>
          <div style={{ fontSize:'11px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em' }}>
            machine monitoring // energy optimization
          </div>
          <div className="term-divider" style={{ marginTop:'12px' }} />
        </div>
        <div className="card">
          <div style={{ fontSize:'11px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'20px' }}>
            &gt; authenticate
          </div>
          {error && <div className="alert alert-error" style={{ marginBottom:'16px', fontSize:'12px' }}>{error}</div>}
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom:'14px' }}>
              <label style={{ display:'block', fontSize:'11px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:'6px' }}>username</label>
              <input className="input" type="text" value={username} onChange={e => setUsername(e.target.value)} placeholder="admin" autoComplete="username" autoFocus required />
            </div>
            <div style={{ marginBottom:'22px' }}>
              <label style={{ display:'block', fontSize:'11px', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:'6px' }}>password</label>
              <input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••••" autoComplete="current-password" required />
            </div>
            <button type="submit" className="btn btn-primary" disabled={loading || !username || !password}
              style={{ justifyContent:'center', padding:'10px', fontSize:'12px', width:'100%' }}>
              {loading ? '> authenticating...' : '> sign in'}
            </button>
          </form>
        </div>
        <p style={{ textAlign:'center', fontSize:'11px', color:'var(--text-muted)', marginTop:'20px' }}>
          GreenOps v2.0.0 // secure access
        </p>
      </div>
    </div>
  );
}
