'use client';

import React, { useState } from 'react';
import api from '../../api';
import Link from 'next/link';

export default function RecoverPage() {
  const [step, setStep] = useState<1 | 2>(1);
  const [mobile, setMobile] = useState('');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [recoveredPin, setRecoveredPin] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleFetchQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await api.get(`/api/auth/question?mobile=${mobile}`);
      setQuestion(res.data.question);
      setStep(2);
    } catch (error: any) {
      console.error('Fetch question failed:', error);
      alert(error.response?.data?.detail || 'Failed to fetch security question.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRecover = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await api.post('/api/auth/recover', {
        mobile,
        answer
      });
      setRecoveredPin(res.data.new_pin);
    } catch (error: any) {
      console.error('Recovery failed:', error);
      alert(error.response?.data?.detail || 'Incorrect answer.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#F9FAFB' }}>
      <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', width: '100%', maxWidth: '400px' }}>
        <h2 style={{ margin: '0 0 1.5rem 0', textAlign: 'center', color: '#111827' }}>Account Recovery</h2>
        
        {!recoveredPin ? (
          step === 1 ? (
            <form onSubmit={handleFetchQuestion} style={{ display: 'flex', flexDirection: 'column' }}>
              <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Enter Mobile Number</label>
              <input type="text" value={mobile} onChange={e => setMobile(e.target.value)} style={{ padding: '0.75rem', marginBottom: '1.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
              <button type="submit" disabled={isLoading} style={{ padding: '0.75rem', backgroundColor: isLoading ? '#9CA3AF' : '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: isLoading ? 'not-allowed' : 'pointer', fontSize: '1rem', marginBottom: '1rem' }}>
                {isLoading ? 'Loading...' : 'Get Security Question'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRecover} style={{ display: 'flex', flexDirection: 'column' }}>
              <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Security Question</label>
              <input type="text" value={question} disabled style={{ padding: '0.75rem', marginBottom: '1rem', border: '1px solid #D1D5DB', borderRadius: '4px', backgroundColor: '#F3F4F6', color: '#6B7280', cursor: 'not-allowed' }} />
              
              <label style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Your Answer</label>
              <input type="text" value={answer} onChange={e => setAnswer(e.target.value)} style={{ padding: '0.75rem', marginBottom: '1.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
              <button type="submit" disabled={isLoading} style={{ padding: '0.75rem', backgroundColor: isLoading ? '#9CA3AF' : '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: isLoading ? 'not-allowed' : 'pointer', fontSize: '1rem', marginBottom: '1rem' }}>
                {isLoading ? 'Verifying...' : 'Recover PIN'}
              </button>
            </form>
          )
        ) : (
          <div style={{ textAlign: 'center' }}>
            <div style={{ padding: '1rem', backgroundColor: '#D1FAE5', color: '#065F46', borderRadius: '4px', marginBottom: '1.5rem', border: '1px solid #34D399' }}>
              <strong>Success!</strong> Your PIN is:<br />
              <span style={{ fontSize: '2rem', letterSpacing: '2px', fontWeight: 'bold', display: 'block', margin: '0.5rem 0' }}>{recoveredPin}</span>
            </div>
            <Link href="/login" style={{ display: 'inline-block', padding: '0.75rem 1.5rem', backgroundColor: '#3B82F6', color: 'white', textDecoration: 'none', borderRadius: '4px', fontWeight: 'bold' }}>Return to Login</Link>
          </div>
        )}
        
        {!recoveredPin && (
          <div style={{ textAlign: 'center', fontSize: '0.85rem', marginTop: '0.5rem' }}>
            <Link href="/login" style={{ color: '#6B7280', textDecoration: 'none' }}>Back to Sign In</Link>
          </div>
        )}
      </div>
    </div>
  );
}