'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AuthProvider, useAuth } from '@/hooks/useAuth';
import AppLayout from '@/components/AppLayout';
import { ReactNode } from 'react';

function Guard({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [loading, isAuthenticated, router]);

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)', gap: '12px',
      }}>
        <div className="spinner" />
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>LOADING...</div>
      </div>
    );
  }
  if (!isAuthenticated) return null;

  return <AppLayout>{children}</AppLayout>;
}

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <Guard>{children}</Guard>
    </AuthProvider>
  );
}
