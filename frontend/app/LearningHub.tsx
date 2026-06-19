'use client';

import React, { useState } from 'react';
import api from '../api';
import { useAppDispatch, useAppSelector } from '../hooks';
import { setTopic, setLanguage, setContent, setIsLoading } from '../learningSlice';

export default function LearningHub() {
  const dispatch = useAppDispatch();
  const { topic, language, content, isLoading } = useAppSelector((state) => state.learning);
  
  const [showArchive, setShowArchive] = useState(false);
  const [archiveContent, setArchiveContent] = useState('');
  const [isSavingArchive, setIsSavingArchive] = useState(false);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;
    
    dispatch(setIsLoading(true));
    try {
      const res = await api.post('/api/learn', { topic, language });
      dispatch(setContent(res.data.content));
    } catch (error) {
      console.error('Failed to generate lesson:', error);
      dispatch(setContent('⚠️ Failed to generate lesson. Please try again.'));
    } finally {
      dispatch(setIsLoading(false));
    }
  };

  const archiveLesson = async () => {
    if (!content) return;
    try {
      await api.post('/api/archive', { user_id: 'auto', content: `--- AI Lesson: ${topic} ---\n\n${content}` });
      alert("Lesson archived successfully for future use!");
    } catch (error) {
      console.error("Archive failed", error);
    }
  };

  const fetchArchive = async () => {
    try {
      const res = await api.get('/api/archive');
      setArchiveContent(res.data.content || '');
      setShowArchive(true);
    } catch (e) {
      console.error("Failed to fetch archive", e);
    }
  };

  const saveArchive = async () => {
    setIsSavingArchive(true);
    try {
      await api.put('/api/archive', { user_id: 'auto', content: archiveContent });
      alert("Archive updated!");
    } catch (e) {
      console.error("Failed to update archive", e);
    } finally {
      setIsSavingArchive(false);
    }
  };

  return (
    <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ marginTop: 0, color: '#111827' }}>📚 AI Learning Hub</h2>
          <p style={{ color: '#6B7280', margin: 0 }}>Instantly generate a structured lesson and quiz on any topic.</p>
        </div>
        <button onClick={() => showArchive ? setShowArchive(false) : fetchArchive()} style={{ padding: '0.5rem 1rem', background: '#374151', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
          {showArchive ? 'Hide Archive' : '📂 View Archive'}
        </button>
      </div>
      
      {showArchive ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <textarea value={archiveContent} onChange={e => setArchiveContent(e.target.value)} style={{ width: '100%', minHeight: '400px', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', fontFamily: 'monospace', resize: 'vertical' }} placeholder="Your persistent archives will appear here..." />
          <button onClick={saveArchive} disabled={isSavingArchive} style={{ padding: '0.75rem 1.5rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', alignSelf: 'flex-start' }}>{isSavingArchive ? 'Saving...' : 'Save Archive Changes'}</button>
        </div>
      ) : (
        <>
      <form onSubmit={handleGenerate} style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
        <input 
          type="text" 
          value={topic} 
          onChange={(e) => dispatch(setTopic(e.target.value))} 
          placeholder="E.g., Python Decorators, Machine Learning Basics..." 
          style={{ flex: 1, minWidth: '250px', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} 
          required 
        />
        <select value={language} onChange={(e) => dispatch(setLanguage(e.target.value))} style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', minWidth: '120px' }}>
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
          <button onClick={archiveLesson} style={{ marginTop: '1rem', padding: '0.75rem 1.5rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
            💾 Archive Lesson
          </button>
        </div>
      )}
        </>
      )}
    </div>
  );
}