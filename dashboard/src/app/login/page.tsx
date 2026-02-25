'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AuthProvider, useAuth } from '@/hooks/useAuth';

function LoginForm() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setError('');
    setLoading(true);
    try {
      await login(username.trim(), password);
      router.replace('/dashboard');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object') setError(detail.message || 'Login failed.');
      else if (typeof detail === 'string') setError(detail);
      else if (err.response?.status === 429) setError('Too many login attempts. Please wait.');
      else setError('Invalid username or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-primary)', padding: '24px', position: 'relative', overflow: 'hidden',
    }} className="grid-bg">
      {/* Subtle glow */}
      <div style={{
        position: 'fixed', top: '30%', left: '50%', transform: 'translateX(-50%)',
        width: '600px', height: '600px', borderRadius: '50%', pointerEvents: 'none',
        background: 'radial-gradient(circle, rgba(0,180,216,0.04) 0%, transparent 70%)',
      }} />

      <div style={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: '380px' }} className="animate-in">
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <rect width="28" height="28" rx="4" fill="rgba(0,180,216,0.12)" stroke="rgba(0,180,216,0.25)" strokeWidth="1"/>
              <path d="M14 6C9.58 6 6 9.58 6 14s3.58 8 8 8 8-3.58 8-8-3.58-8-8-8zm0 2a6 6 0 1 1 0 12A6 6 0 0 1 14 8z" fill="rgba(0,180,216,0.4)"/>
              <path d="M11 14.5l2 2 4-4.5" stroke="#00b4d8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              GreenOps<span className="cursor" />
            </span>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Infrastructure · Energy · Control
          </div>
        </div>

        {/* Divider */}
        <div style={{ borderTop: '1px solid var(--border)', marginBottom: '24px', position: 'relative' }}>
          <span style={{
            position: 'absolute', top: '-9px', left: '0',
            background: 'var(--bg-primary)', paddingRight: '12px',
            fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.05em',
          }}>
            // AUTH
          </span>
        </div>

        {/* Card */}
        <div style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border)',
          padding: '24px', borderRadius: 'var(--radius)',
        }}>
          {error && (
            <div style={{
              background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)',
              color: 'var(--red)', padding: '10px 14px', borderRadius: 'var(--radius)',
              fontSize: '13px', marginBottom: '20px',
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>
                username
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="username"
                autoFocus
                required
                style={{
                  width: '100%', padding: '10px 12px',
                  background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)', color: 'var(--text-primary)',
                  fontFamily: 'var(--font)', fontSize: '14px', outline: 'none',
                  transition: 'border-color var(--transition)',
                }}
                onFocus={e => { e.target.style.borderColor = 'var(--accent)'; }}
                onBlur={e => { e.target.style.borderColor = 'var(--border)'; }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>
                password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
                style={{
                  width: '100%', padding: '10px 12px',
                  background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)', color: 'var(--text-primary)',
                  fontFamily: 'var(--font)', fontSize: '14px', outline: 'none',
                  transition: 'border-color var(--transition)',
                }}
                onFocus={e => { e.target.style.borderColor = 'var(--accent)'; }}
                onBlur={e => { e.target.style.borderColor = 'var(--border)'; }}
              />
            </div>

            <button
              type="submit"
              disabled={loading || !username || !password}
              style={{
                width: '100%', padding: '11px',
                background: loading ? 'var(--accent-dim)' : 'var(--accent)',
                border: '1px solid var(--accent)',
                borderRadius: 'var(--radius)', color: loading ? 'var(--accent)' : '#0e0e0e',
                fontFamily: 'var(--font)', fontSize: '13px', fontWeight: '700',
                letterSpacing: '0.06em', cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                transition: 'all var(--transition)',
              }}
            >
              {loading ? (
                <>
                  <div className="spinner" style={{ width: '14px', height: '14px', borderTopColor: 'var(--accent)' }} />
                  AUTHENTICATING...
                </>
              ) : '> SIGN IN'}
            </button>
          </form>
        </div>

        <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
          GREENOPS v2.0.0 · SECURE TERMINAL
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <AuthProvider>
      <LoginForm />
    </AuthProvider>
  );
}
