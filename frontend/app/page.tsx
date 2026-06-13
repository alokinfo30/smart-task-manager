'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import LogoutButton from './LogoutButton';
import MainTabs from './MainTabs';
import { useAuth } from '../AuthContext';

export default function MainPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  
  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  if (loading) return <p style={{ padding: '2rem', textAlign: 'center' }}>Loading workspace...</p>;

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', maxWidth: '1400px', margin: '0 auto' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '1px solid #eee' }}>
        <h1 style={{ margin: 0 }}>🤖 Smart Task Manager</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#F3F4F6', padding: '0.4rem 1rem', borderRadius: '50px' }}>
              <span style={{ fontSize: '1.2rem' }}>{user.avatar || '👤'}</span>
              <span style={{ fontWeight: 'bold', color: '#374151' }}>{user.name || user.user_id}</span>
            </div>
          )}
          <LogoutButton />
        </div>
      </header>

      <main>
        {user ? (
          <MainTabs session={user.user_id} />
        ) : (
          <p>Please log in to access your workspace.</p>
        )}
      </main>
    </div>
  );
}