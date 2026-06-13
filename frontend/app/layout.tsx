import React from 'react';
import type { Metadata, Viewport } from 'next';
import { AuthProvider } from '../AuthContext';


export const viewport: Viewport = {
  themeColor: '#2563EB',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata: Metadata = {
  title: 'Smart Task Manager',
  description: 'AI-powered offline-first task and expense manager.',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Task Manager',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="manifest" href="/manifest.json" />
      </head>
      <body suppressHydrationWarning>
        <AuthProvider>
        {children}
        </AuthProvider>
      </body>
    </html>
  );
}