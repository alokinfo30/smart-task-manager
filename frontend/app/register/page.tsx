'use client';

import React, { useState } from 'react';
import api from '../../api';
import Link from 'next/link';

const SECURITY_QUESTIONS = [
  "What was the name of your first pet?",
  "In what city were you born?",
  "What is your mother's maiden name?",
  "What was the name of your first school?",
];

export default function RegisterPage() {
  const [mobile, setMobile] = useState('');
  const [pin, setPin] = useState('');
  const [question, setQuestion] = useState(SECURITY_QUESTIONS[0]);
  const [answer, setAnswer] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await api.post('/api/auth/register', {
        mobile,
        pin,
        security_question: question,
        security_answer: answer
      });
      // A successful registration drops a cookie. Redirecting to root triggers auto-login.
      window.location.href = '/';
    } catch (error: any) {
      console.error('Registration failed:', error);
      alert(error.response?.data?.detail || 'Failed to register. Mobile might already exist.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#F9FAFB' }}>
      <form onSubmit={handleSubmit} style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', width: '100%', maxWidth: '400px' }}>
        <h2 style={{ margin: '0 0 1.5rem 0', textAlign: 'center', color: '#111827' }}>Create Account</h2>
        
        <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Mobile Number</label>
        <input type="text" value={mobile} onChange={e => setMobile(e.target.value)} style={{ padding: '0.75rem', marginBottom: '1rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        
        <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>6-Digit PIN</label>
        <input type="password" value={pin} onChange={e => setPin(e.target.value)} maxLength={6} style={{ padding: '0.75rem', marginBottom: '1rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        
        <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Security Question</label>
        <select value={question} onChange={e => setQuestion(e.target.value)} style={{ padding: '0.75rem', marginBottom: '1rem', border: '1px solid #D1D5DB', borderRadius: '4px', backgroundColor: 'white' }} required>
          {SECURITY_QUESTIONS.map(q => (
            <option key={q} value={q}>{q}</option>
          ))}
        </select>
        
        <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Security Answer</label>
        <input type="text" value={answer} onChange={e => setAnswer(e.target.value)} style={{ padding: '0.75rem', marginBottom: '1.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        
        <button type="submit" disabled={isLoading} style={{ padding: '0.75rem', backgroundColor: isLoading ? '#9CA3AF' : '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: isLoading ? 'not-allowed' : 'pointer', fontSize: '1rem', marginBottom: '1rem' }}>
          {isLoading ? 'Registering...' : 'Register'}
        </button>

        <div style={{ textAlign: 'center', fontSize: '0.85rem' }}>
          <Link href="/login" style={{ color: '#3B82F6', textDecoration: 'none' }}>Already have an account? Sign in</Link>
        </div>
      </form>
    </div>
  );
}