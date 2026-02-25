import React from 'react';
export default function LoadingScreen() {
  return (
    <div style={{ minHeight:'100vh', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', background:'var(--bg-primary)', gap:'12px' }}>
      <div style={{ fontSize:'20px', fontWeight:'700', color:'var(--text-primary)' }}>
        GREENOPS<span className="cursor" />
      </div>
      <div className="spinner" />
      <p style={{ color:'var(--text-muted)', fontSize:'11px', textTransform:'uppercase', letterSpacing:'0.1em' }}>Initializing...</p>
    </div>
  );
}
