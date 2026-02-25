import React from 'react';

export default function LoadingScreen() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-primary)',
      gap: '16px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <rect width="32" height="32" rx="8" fill="var(--green-primary)" fillOpacity="0.15"/>
          <path d="M16 6C10.477 6 6 10.477 6 16s4.477 10 10 10 10-4.477 10-10S21.523 6 16 6zm0 3a7 7 0 1 1 0 14A7 7 0 0 1 16 9z" fill="var(--green-primary)" fillOpacity="0.3"/>
          <path d="M13 16.5l2 2 4-4" stroke="var(--green-primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)' }}>GreenOps</span>
      </div>
      <div className="spinner" />
      <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Loading...</p>
    </div>
  );
}
