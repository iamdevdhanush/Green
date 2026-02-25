'use client';
import { useAuth } from '@/hooks/useAuth';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ReactNode } from 'react';

const NAV = [
  {
    href: '/dashboard', label: 'dashboard', cmd: '> status',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
        <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
      </svg>
    ),
  },
  {
    href: '/machines', label: 'machines', cmd: '> ls /machines',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
      </svg>
    ),
  },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.replace('/login');
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Sidebar */}
      <aside style={{
        width: '220px', flexShrink: 0,
        background: 'var(--bg-secondary)', borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        position: 'sticky', top: 0, height: '100vh',
      }}>
        {/* Logo */}
        <div style={{ padding: '20px 16px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
              <rect width="22" height="22" rx="3" fill="rgba(0,180,216,0.12)" stroke="rgba(0,180,216,0.25)" strokeWidth="1"/>
              <path d="M11 4C7.13 4 4 7.13 4 11s3.13 7 7 7 7-3.13 7-7-3.13-7-7-7zm0 1.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11z" fill="rgba(0,180,216,0.4)"/>
              <path d="M9 11l1.5 1.5 3-3.5" stroke="#00b4d8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              GreenOps
            </span>
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', paddingLeft: '30px' }}>
            ENERGY · MONITOR
          </div>
        </div>

        {/* Divider label */}
        <div style={{ padding: '12px 16px 8px', fontSize: '10px', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          // navigation
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '0 10px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {NAV.map((item) => {
            const active = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '9px 10px', borderRadius: 'var(--radius)',
                  color: active ? 'var(--accent)' : 'var(--text-secondary)',
                  background: active ? 'var(--accent-dim)' : 'transparent',
                  border: `1px solid ${active ? 'var(--accent-border)' : 'transparent'}`,
                  textDecoration: 'none', fontSize: '13px',
                  transition: 'all var(--transition)',
                }}
              >
                {item.icon}
                <span style={{ fontWeight: active ? '600' : '400' }}>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div style={{ padding: '12px 10px', borderTop: '1px solid var(--border)' }}>
          <div style={{ padding: '8px 10px', marginBottom: '4px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.05em', marginBottom: '2px' }}>
              // session
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: '500' }}>{user?.username}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{user?.role}</div>
          </div>
          <button
            onClick={handleLogout}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
              padding: '8px 10px', borderRadius: 'var(--radius)',
              background: 'none', border: '1px solid transparent',
              color: 'var(--text-muted)', fontFamily: 'var(--font)', fontSize: '12px',
              cursor: 'pointer', transition: 'all var(--transition)',
              letterSpacing: '0.03em',
            }}
            onMouseEnter={e => {
              const btn = e.currentTarget;
              btn.style.color = 'var(--red)';
              btn.style.background = 'var(--red-dim)';
              btn.style.borderColor = 'rgba(239,68,68,0.15)';
            }}
            onMouseLeave={e => {
              const btn = e.currentTarget;
              btn.style.color = 'var(--text-muted)';
              btn.style.background = 'none';
              btn.style.borderColor = 'transparent';
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            logout
          </button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, overflow: 'auto', padding: '28px 32px' }}>
        {children}
      </main>
    </div>
  );
}
