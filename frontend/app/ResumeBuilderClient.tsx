'use client';

import React, { useState, useEffect } from 'react';
import { fetchWithAuth } from './fetchWithAuth';

export default function ResumeBuilderClient() {
  const [userInfo, setUserInfo] = useState('');
  const [jobDesc, setJobDesc] = useState('');
  const [language, setLanguage] = useState('English');
  const [content, setContent] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [savedProfile, setSavedProfile] = useState('');

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const res = await fetchWithAuth(`${API_BASE_URL}/api/resume/profile`);
        if (res.ok) {
          const data = await res.json();
          setSavedProfile(data.content || '');
        }
      } catch (e) { console.error(e); }
    };
    loadProfile();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    setIsLoading(true);
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/parse-pdf`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.text) setUserInfo(prev => prev + '\n\n--- Parsed PDF ---\n' + data.text);
      else alert("Could not extract text from PDF.");
    } catch (e) { console.error("PDF upload failed", e); alert("Failed to parse PDF."); }
    finally { setIsLoading(false); }
  };

  const handleGenerate = async () => {
    const combinedInfo = userInfo.trim() ? userInfo : savedProfile;
    if (!combinedInfo.trim() || !jobDesc.trim()) return alert("Please provide user background and a job description.");
    
    setIsLoading(true);
    try {
      if (userInfo.trim()) {
        await fetchWithAuth(`${API_BASE_URL}/api/resume/profile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: userInfo })
        });
        setSavedProfile(userInfo);
      }

      const activeLanguage = localStorage.getItem('userLocationLanguage') || language;
      const res = await fetchWithAuth(`${API_BASE_URL}/api/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_info: combinedInfo, job_desc: jobDesc, language: activeLanguage })
      });
      const data = await res.json();
      setContent(data.content);
    } catch (error) {
      console.error('Failed to generate resume:', error);
      setContent('⚠️ Failed to generate resume. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const downloadTxt = () => {
    const element = document.createElement("a");
    const file = new Blob([content], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = "Tailored_Resume.txt";
    document.body.appendChild(element); 
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, color: '#111827' }}>📄 AI Resume Builder</h2>
        {content && <button onClick={downloadTxt} style={{ padding: '0.5rem 1rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>📥 Download Text</button>}
      </div>
      
      {savedProfile && <div style={{ padding: '1rem', background: '#D1FAE5', color: '#047857', borderRadius: '4px', marginBottom: '1rem' }}>✅ Saved Resume Profile is loaded and active.</div>}

      <div style={{ display: 'flex', gap: '2rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '300px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <label style={{ fontWeight: 'bold', color: '#374151' }}>1. Your Background</label>
            <label style={{ cursor: 'pointer', color: '#3B82F6', fontSize: '0.85rem', fontWeight: 'bold' }}>📎 Upload PDF <input type="file" accept=".pdf" onChange={handleFileUpload} style={{ display: 'none' }} /></label>
          </div>
          <textarea value={userInfo} onChange={e => setUserInfo(e.target.value)} placeholder="Paste your existing resume text, LinkedIn profile, or bullet points here..." style={{ width: '100%', height: '200px', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box', fontFamily: 'inherit' }} />
        </div>
        <div style={{ flex: 1, minWidth: '300px' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#374151' }}>2. Target Job Description</label>
          <textarea value={jobDesc} onChange={e => setJobDesc(e.target.value)} placeholder="Paste the job description you are applying for..." style={{ width: '100%', height: '200px', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box', fontFamily: 'inherit' }} />
        </div>
      </div>

      <button onClick={handleGenerate} disabled={isLoading} style={{ width: '100%', padding: '1rem', background: isLoading ? '#9CA3AF' : '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: isLoading ? 'not-allowed' : 'pointer', fontWeight: 'bold', fontSize: '1rem', marginBottom: '2rem' }}>
        {isLoading ? '✨ Analyzing and Tailoring Resume...' : '✨ Generate Tailored Resume'}
      </button>

      {content && (
        <div style={{ background: '#F9FAFB', padding: '2rem', borderRadius: '8px', border: '1px solid #E5E7EB', whiteSpace: 'pre-wrap', fontFamily: 'monospace', lineHeight: '1.6', color: '#111827' }}>
          {content}
        </div>
      )}
    </div>
  );
}