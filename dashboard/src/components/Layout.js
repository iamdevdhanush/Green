import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const NAV = [
  { to: '/', label: '[ dashboard ]', exact: true },
  { to: '/machines', label: '[ machines ]', exact: false },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const handleLogout = async () => { await logout(); navigate('/login'); };

  return (
    <div style={{ display:'flex', minHeight:'100vh', background:'var(--bg-primary)' }}>
      <aside style={{ width:'220px', flexShrink:0, background:'var(--bg-secondary)', borderRight:'1px solid var(--border)', display:'flex', flexDirection:'column', position:'sticky', top:0, height:'100vh' }}>
        <div style={{ padding:'20px 16px', borderBottom:'1px solid var(--border)' }}>
          <div style={{ fontSize:'15px', fontWeight:'700', color:'var(--cyan)', letterSpacing:'0.05em' }}>
            GREENOPS<span className="cursor" />
          </div>
          <div style={{ fontSize:'10px', color:'var(--text-muted)', marginTop:'2px', textTransform:'uppercase', letterSpacing:'0.1em' }}>
            v2.0.0 // energy monitor
          </div>
        </div>
        <nav style={{ flex:1, padding:'12px 8px', display:'flex', flexDirection:'column', gap:'2px' }}>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.exact}
              style={({ isActive }) => ({
                display:'block', padding:'8px 10px', borderRadius:'var(--radius-sm)',
                color: isActive ? 'var(--cyan)' : 'var(--text-muted)',
                textDecoration:'none', fontSize:'12px', fontWeight:'500',
                background: isActive ? 'var(--cyan-dim)' : 'none',
                border: isActive ? '1px solid var(--cyan-border)' : '1px solid transparent',
                transition:'all var(--transition)', letterSpacing:'0.03em',
              })}
            >{item.label}</NavLink>
          ))}
        </nav>
        <div style={{ padding:'12px 8px', borderTop:'1px solid var(--border)' }}>
          <div style={{ padding:'8px 10px', fontSize:'11px', color:'var(--text-muted)', marginBottom:'4px' }}>
            <span style={{ color:'var(--text-secondary)' }}>{user?.username}</span>
            <span style={{ marginLeft:'6px', color:'var(--cyan)', fontSize:'10px' }}>#{user?.role}</span>
          </div>
          <button onClick={handleLogout}
            style={{ width:'100%', display:'block', padding:'7px 10px', background:'none', border:'1px solid transparent', borderRadius:'var(--radius-sm)', color:'var(--text-muted)', fontSize:'12px', fontFamily:'var(--font)', cursor:'pointer', textAlign:'left', transition:'all var(--transition)', letterSpacing:'0.03em' }}
            onMouseEnter={e => { e.currentTarget.style.color='var(--red-primary)'; e.currentTarget.style.background='var(--red-bg)'; e.currentTarget.style.borderColor='rgba(248,113,113,0.2)'; }}
            onMouseLeave={e => { e.currentTarget.style.color='var(--text-muted)'; e.currentTarget.style.background='none'; e.currentTarget.style.borderColor='transparent'; }}
          >[ logout ]</button>
        </div>
      </aside>
      <main style={{ flex:1, overflow:'auto', padding:'28px 32px' }}>
        <Outlet />
      </main>
    </div>
  );
}
