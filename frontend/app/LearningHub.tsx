'use client';

import React, { useState } from 'react';
import api from '../api';

export default function LearningHub() {
  const [topic, setTopic] = useState('');
  const [language, setLanguage] = useState('English');
  const [content, setContent] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;
    
    setIsLoading(true);
    try {
      const res = await api.post('/api/learn', { topic, language });
      setContent(res.data.content);
    } catch (error) {
      console.error('Failed to generate lesson:', error);
      setContent('⚠️ Failed to generate lesson. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <h2 style={{ marginTop: 0, color: '#111827' }}>📚 AI Learning Hub</h2>
      <p style={{ color: '#6B7280', marginBottom: '1.5rem' }}>Instantly generate a structured lesson and quiz on any topic.</p>
      
      <form onSubmit={handleGenerate} style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
        <input 
          type="text" 
          value={topic} 
          onChange={(e) => setTopic(e.target.value)} 
          placeholder="E.g., Python Decorators, Machine Learning Basics..." 
          style={{ flex: 1, minWidth: '250px', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} 
          required 
        />
        <select value={language} onChange={(e) => setLanguage(e.target.value)} style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', minWidth: '120px' }}>
          <option value="English">English</option>
          <option value="Spanish">Spanish</option>
          <option value="Hindi">Hindi</option>
          <option value="French">French</option>
        </select>
        <button type="submit" disabled={isLoading} style={{ padding: '0.75rem 1.5rem', background: isLoading ? '#9CA3AF' : '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: isLoading ? 'not-allowed' : 'pointer', fontWeight: 'bold' }}>
          {isLoading ? 'Generating...' : '🚀 Generate Lesson'}
        </button>
      </form>

      {content && (
        <div style={{ background: '#F9FAFB', padding: '1.5rem', borderRadius: '8px', border: '1px solid #E5E7EB' }}>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6', color: '#374151', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            {content}
          </div>
        </div>
      )}
    </div>
  );
}