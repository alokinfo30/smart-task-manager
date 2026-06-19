'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import MainTabs from './MainTabs';
import { useAuth } from '../AuthContext';
import ProfileClient from './ProfileClient';

export default function MainPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [showProfile, setShowProfile] = useState(false);
  const [showEditProfile, setShowEditProfile] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  // Close profile dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setShowProfile(false);
        setShowEditProfile(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  if (loading) return <p style={{ padding: '2rem', textAlign: 'center' }}>Loading workspace...</p>;

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Floating Profile Dropdown (Top Right) */}
      {user && (
        <div ref={profileRef} style={{ position: 'fixed', top: '1rem', right: '1rem', zIndex: 50 }}>
          <button onClick={() => { setShowProfile(!showProfile); setShowEditProfile(false); }} style={{ borderRadius: '50%', width: '40px', height: '40px', background: '#3B82F6', color: 'white', border: 'none', cursor: 'pointer', fontSize: '1.2rem', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 4px rgba(0,0,0,0.1)', overflow: 'hidden', padding: 0 }}>
            {user?.avatar ? <img src={user.avatar} alt="Profile" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : '👤'}
          </button>
          
          {showProfile && (
            <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: '0.5rem', background: 'white', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '0', zIndex: 100, boxShadow: '0 4px 6px rgba(0,0,0,0.1)', width: '90vw', maxWidth: '600px', maxHeight: '80vh', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
              {!showEditProfile ? (
                <div style={{ display: 'flex', flexDirection: 'column', minWidth: '250px' }}>
                  <div style={{ padding: '1rem', borderBottom: '1px solid #E5E7EB', background: '#F9FAFB', borderRadius: '8px 8px 0 0' }}>
                    <p style={{ margin: 0, fontWeight: 'bold', color: '#374151' }}>Logged in as:</p>
                    <p style={{ margin: 0, color: '#6B7280', fontSize: '0.9rem' }}>{user?.name || user?.user_id}</p>
                  </div>
                  <button onClick={() => setShowEditProfile(true)} style={{ padding: '1rem', textAlign: 'left', background: 'none', border: 'none', borderBottom: '1px solid #E5E7EB', cursor: 'pointer', fontSize: '1rem', color: '#374151' }}>
                    ✏️ Edit Profile
                  </button>
                  <button onClick={logout} style={{ padding: '1rem', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem', color: '#EF4444', fontWeight: 'bold', borderRadius: '0 0 8px 8px' }}>
                    🚪 Logout
                  </button>
                </div>
              ) : (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderBottom: '1px solid #E5E7EB', background: '#F9FAFB', borderRadius: '8px 8px 0 0' }}>
                    <button onClick={() => setShowEditProfile(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3B82F6', fontSize: '1rem', fontWeight: 'bold' }}>← Back</button>
                    <button onClick={logout} style={{ background: '#EF4444', color: 'white', border: 'none', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>Logout</button>
                  </div>
                  <ProfileClient />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '1px solid #eee' }}>
        <h1 style={{ margin: 0 }}>🤖 Smart Task Manager</h1>
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