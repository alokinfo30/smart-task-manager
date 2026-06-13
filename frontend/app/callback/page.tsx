'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import api from '../../api';

const SECURITY_QUESTIONS = [
  "What was the name of your first pet?",
  "In what city were you born?",
  "What is your mother's maiden name?",
  "What was the name of your first school?",
];

function CallbackContent() {
  const searchParams = useSearchParams();
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('Processing Google Sign-In...');
  
  // Form fields to link account
  const [mobile, setMobile] = useState('');
  const [pin, setPin] = useState('');
  const [question, setQuestion] = useState(SECURITY_QUESTIONS[0]);
  const [answer, setAnswer] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (code && state && !email) {
      api.post('/api/auth/google/callback', {
        code,
        state,
        redirect_uri: `${window.location.origin}/auth/callback`
      }).then(res => {
        setEmail(res.data.email);
        setStatus('');
      }).catch(err => {
        console.error('SSO Callback error:', err);
        setStatus('Authentication failed. Please return to login.');
      });
    }
  }, [code, state, email]);

  const handleComplete = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await api.post('/api/auth/google/complete', {
        email,
        mobile,
        pin,
        security_question: question,
        security_answer: answer
      });
      // Drop cookie and return to workspace
      window.location.href = '/';
    } catch (err: any) {
      console.error('SSO Complete error:', err);
      alert(err.response?.data?.detail || 'Failed to complete registration.');
      setIsLoading(false);
    }
  };

  if (status) {
    return <p style={{ textAlign: 'center', marginTop: '5rem', color: '#4B5563' }}>{status}</p>;
  }

  if (email) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#F9FAFB' }}>
        <form onSubmit={handleComplete} style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', width: '100%', maxWidth: '400px' }}>
          <h2 style={{ margin: '0 0 0.5rem 0', textAlign: 'center', color: '#111827' }}>Link Your Account</h2>
          <p style={{ textAlign: 'center', color: '#6B7280', fontSize: '0.85rem', marginBottom: '1.5rem' }}>Authenticated as <strong>{email}</strong></p>
          
          <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Mobile Number</label>
          <input type="text" value={mobile} onChange={e => setMobile(e.target.value)} placeholder="Existing or new mobile..." style={{ padding: '0.75rem', marginBottom: '1rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
          
          <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>6-Digit PIN</label>
          <input type="password" value={pin} onChange={e => setPin(e.target.value)} maxLength={6} placeholder="Enter PIN to link/create" style={{ padding: '0.75rem', marginBottom: '1rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
          
          <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Security Question</label>
          <select value={question} onChange={e => setQuestion(e.target.value)} style={{ padding: '0.75rem', marginBottom: '1rem', border: '1px solid #D1D5DB', borderRadius: '4px', backgroundColor: 'white' }} required>
            {SECURITY_QUESTIONS.map(q => (
              <option key={q} value={q}>{q}</option>
            ))}
          </select>
          
          <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Security Answer</label>
          <input type="text" value={answer} onChange={e => setAnswer(e.target.value)} style={{ padding: '0.75rem', marginBottom: '1.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
          
          <button type="submit" disabled={isLoading} style={{ padding: '0.75rem', backgroundColor: isLoading ? '#9CA3AF' : '#10B981', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: isLoading ? 'not-allowed' : 'pointer', fontSize: '1rem' }}>
            {isLoading ? 'Completing...' : 'Complete Registration'}
          </button>
        </form>
      </div>
    );
  }

  return null;
}

export default function CallbackPage() {
  // Next.js 13+ requires useSearchParams to be wrapped in a suspense boundary
  return <Suspense fallback={<p style={{ textAlign: 'center', marginTop: '5rem' }}>Loading...</p>}><CallbackContent /></Suspense>;
}