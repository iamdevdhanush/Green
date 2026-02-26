'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    // localStorage is only available in the browser (not during SSR)
    const token = typeof window !== 'undefined'
      ? localStorage.getItem('access_token')
      : null;
    if (token) {
      router.replace('/dashboard');
    } else {
      router.replace('/login');
    }
  }, [router]);
  return null;
}
