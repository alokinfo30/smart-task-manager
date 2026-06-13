'use client';

import React, { useState } from 'react';
import { useAuth } from '../../AuthContext';
import api from '../../api';
import Link from 'next/link';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
    } catch (error) {
      console.error('Login failed:', error);
      alert('Failed to login. Please check your credentials.');
    }
  };

  const handleDemoLogin = async () => {
    try {
      await login('demo_user', '000000');
    } catch (error) {
      console.error('Demo login failed:', error);
    }
  };

  const handleGoogleSSO = async () => {
    try {
      // We use the current origin as redirect_uri for OAuth completion
      const redirectUri = `${window.location.origin}/auth/callback`;
      const res = await api.get(`/api/auth/google/url?redirect_uri=${encodeURIComponent(redirectUri)}`);
      window.location.href = res.data.url;
    } catch (error) {
      console.error('Google SSO failed:', error);
      alert('Failed to initialize Google SSO. Is it configured in the backend?');
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#F9FAFB' }}>
      <form onSubmit={handleSubmit} style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', width: '100%', maxWidth: '400px' }}>
        <h2 style={{ margin: '0 0 1.5rem 0', textAlign: 'center', color: '#111827' }}>Sign In</h2>
        
        <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Mobile Number</label>
        <input type="text" value={username} onChange={e => setUsername(e.target.value)} style={{ padding: '0.75rem', marginBottom: '1rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        
        <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>6-Digit PIN</label>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} maxLength={6} style={{ padding: '0.75rem', marginBottom: '1.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        
        <button type="submit" style={{ padding: '0.75rem', backgroundColor: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', fontSize: '1rem', marginBottom: '1rem' }}>
          Login
        </button>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
          <Link href="/register" style={{ color: '#3B82F6', textDecoration: 'none' }}>Create Account</Link>
          <Link href="/recover" style={{ color: '#3B82F6', textDecoration: 'none' }}>Forgot PIN?</Link>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <button type="button" onClick={handleGoogleSSO} style={{ padding: '0.75rem', backgroundColor: 'white', color: '#374151', border: '1px solid #D1D5DB', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', fontSize: '0.9rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
            🌐 Sign in with Google
          </button>
          <button type="button" onClick={handleDemoLogin} style={{ padding: '0.75rem', backgroundColor: '#10B981', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', fontSize: '0.9rem' }}>
            🚀 Login as Demo User
          </button>
        </div>
      </form>
    </div>
  );
}