'use client';

import React, { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

const SECURITY_QUESTIONS = [
  "Select to update...",
  "What was the name of your first pet?",
  "In what city were you born?",
  "What is your mother's maiden name?",
  "What was the name of your first school?",
];

export default function ProfileClient() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState('');
  const [mobile, setMobile] = useState('');
  const [email, setEmail] = useState('');
  const [avatar, setAvatar] = useState('👤');
  const [pin, setPin] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState(SECURITY_QUESTIONS[0]);
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [status, setStatus] = useState('');

  // Pre-fill the form when the user context loads
  useEffect(() => {
    if (user) {
      setName(user.name || '');
      setMobile(user.user_id || '');
      setEmail(user.email || '');
      setAvatar(user.avatar || '👤');
    }
  }, [user]);

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (securityQuestion !== SECURITY_QUESTIONS[0] && !securityAnswer) {
      return alert("Please provide a security answer if you are updating your security question.");
    }
    setStatus('Updating...');
    try {
      await api.put('/api/profile/edit', {
        name,
        email,
        pin,
        avatar,
        security_question: securityQuestion === SECURITY_QUESTIONS[0] ? "" : securityQuestion,
        security_answer: securityAnswer
      });
      // Refresh global user context to reflect changes everywhere
      const response = await api.get('/api/auth/me');
      setUser(response.data);
      
      setStatus('✅ Profile updated successfully!');
      setPin(''); // Clear the PIN field for security
      setSecurityAnswer('');
      setTimeout(() => setStatus(''), 4000); // Hide banner after 4 seconds
    } catch (error) {
      console.error("Failed to update profile", error);
      setStatus('❌ Failed to update profile.');
      setTimeout(() => setStatus(''), 4000);
    }
  };

  const handleDeleteAccount = async () => {
    const confirm = window.confirm("🚨 Are you ABSOLUTELY sure you want to delete your account?\n\nThis action cannot be undone. All your tasks, expenses, routines, and archives will be lost.");
    if (!confirm) return;
    try {
      await api.delete('/api/profile/delete');
      window.location.href = '/login'; // Redirect drops the session and returns to login
    } catch (e) {
      alert("Failed to delete account. Please try again later.");
    }
  };

  const availableAvatars = ['👤', '👨‍💻', '👩‍💻', '🤖', '🐶', '🐱', '🦄', '🚀', '🌟', '⚡'];

  return (
    <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', maxWidth: '600px', margin: '0 auto' }}>
      <h2 style={{ marginTop: 0, color: '#111827' }}>👤 Edit Profile</h2>
      
      {status && (
        <div style={{ padding: '1rem', marginBottom: '1.5rem', borderRadius: '4px', background: status.includes('✅') ? '#D1FAE5' : status.includes('❌') ? '#FEE2E2' : '#E0E7FF', color: status.includes('✅') ? '#065F46' : status.includes('❌') ? '#991B1B' : '#3730A3', fontWeight: 'bold' }}>
          {status}
        </div>
      )}

      <form onSubmit={handleUpdate} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Choose Avatar</label>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {availableAvatars.map(a => (
              <button key={a} type="button" onClick={() => setAvatar(a)} style={{ fontSize: '2rem', padding: '0.5rem', border: avatar === a ? '2px solid #3B82F6' : '1px solid #D1D5DB', borderRadius: '8px', background: avatar === a ? '#EFF6FF' : 'white', cursor: 'pointer', transition: 'all 0.2s' }}>{a}</button>
            ))}
          </div>
        </div>

      <div><label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Mobile Number</label><input type="text" value={mobile} disabled style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box', backgroundColor: '#F3F4F6', color: '#6B7280', cursor: 'not-allowed' }} title="Mobile number cannot be changed" /></div>
        <div><label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Display Name</label><input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Your Name" style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box' }} /></div>
        <div><label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>Email Address</label><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="your@email.com" style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box' }} /></div>
        <div><label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>New PIN (Optional)</label><input type="password" value={pin} onChange={e => setPin(e.target.value)} maxLength={6} placeholder="Leave blank to keep your current 6-digit PIN" style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box' }} /></div>
        
        <div style={{ padding: '1.5rem', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: '8px', marginTop: '1rem' }}>
          <h3 style={{ margin: '0 0 1rem 0', color: '#374151', fontSize: '1.1rem' }}>Security Question Override</h3>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#4B5563', fontSize: '0.9rem' }}>New Security Question</label>
          <select value={securityQuestion} onChange={e => setSecurityQuestion(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box', marginBottom: '1rem', backgroundColor: 'white' }}>
            {SECURITY_QUESTIONS.map(q => <option key={q} value={q}>{q}</option>)}
          </select>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#4B5563', fontSize: '0.9rem' }}>New Security Answer</label>
          <input type="text" value={securityAnswer} onChange={e => setSecurityAnswer(e.target.value)} placeholder="Enter new answer..." style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box' }} disabled={securityQuestion === SECURITY_QUESTIONS[0]} />
        </div>

        <button type="submit" style={{ padding: '1rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '1rem' }}>💾 Save Profile</button>
      </form>

      <div style={{ marginTop: '3rem', padding: '1.5rem', border: '1px solid #FCA5A5', borderRadius: '8px', background: '#FEF2F2' }}>
        <h3 style={{ marginTop: 0, color: '#991B1B' }}>Danger Zone</h3>
        <p style={{ color: '#7F1D1D', fontSize: '0.9rem', marginBottom: '1rem' }}>Once you delete your account, there is no going back. Please be certain.</p>
        <button type="button" onClick={handleDeleteAccount} style={{ padding: '0.75rem 1.5rem', background: '#EF4444', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>🗑️ Delete Account</button>
      </div>
    </div>
  );
}