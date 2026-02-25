import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'GreenOps — Infrastructure Monitor',
  description: 'Machine monitoring and energy optimization platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
