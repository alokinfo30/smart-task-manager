'use client';

import React, { useState, useEffect } from 'react';
import { fetchWithAuth } from './fetchWithAuth';

export default function ResumeBuilder() {
  const [file, setFile] = useState<File | null>(null);
  const [manualDetails, setManualDetails] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [savedProfile, setSavedProfile] = useState('');
  const [generatedResume, setGeneratedResume] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    // Load the archived resume profile
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

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobDescription.trim()) return alert("Job Description is required");
    
    setIsLoading(true);
    try {
      let combinedInfo = savedProfile;

      // If a new PDF is uploaded, parse it and update the archive
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        
        // Note: For FormData, we omit Content-Type header so the browser sets the boundary correctly
        const token = document.cookie.split('; ').find(row => row.startsWith('stm_token='))?.split('=')[1];
        const uploadRes = await fetch(`${API_BASE_URL}/api/parse-pdf`, {
          method: 'POST',
          headers: token ? { 'Authorization': `Bearer ${token}` } : {},
          body: formData
        });
        
        const uploadData = await uploadRes.json();
        if (uploadData.text) combinedInfo = uploadData.text;
      }

      // Combine parsed/archived PDF with any manual overrides
      if (manualDetails.trim()) {
        combinedInfo += "\n\n" + manualDetails;
      }

      if (!combinedInfo.trim()) {
        setIsLoading(false);
        return alert("Please upload a resume or provide manual details.");
      }

      // Automatically archive the newest profile
      await fetchWithAuth(`${API_BASE_URL}/api/resume/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: combinedInfo })
      });
      setSavedProfile(combinedInfo);

      // Generate Tailored Resume
      const language = localStorage.getItem('userLocationLanguage') || 'English';
      const res = await fetchWithAuth(`${API_BASE_URL}/api/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_info: combinedInfo, job_desc: jobDescription, language })
      });
      
      const data = await res.json();
      setGeneratedResume(data.content);
    } catch (err) {
      console.error(err);
      alert("Generation failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '2rem', background: 'white', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <h2 style={{ marginTop: 0 }}>📄 AI Tailored Resume Builder</h2>
      <p style={{ color: '#6B7280' }}>Upload your current resume (PDF) to permanently archive your profile, then paste a job description to get a tailored ATS-friendly response.</p>
      
      {savedProfile && <div style={{ padding: '1rem', background: '#D1FAE5', color: '#047857', borderRadius: '4px', marginBottom: '1rem' }}>✅ Saved Resume Profile is loaded and active.</div>}

      <form onSubmit={handleGenerate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ padding: '1rem', border: '1px dashed #D1D5DB', borderRadius: '8px', background: '#F9FAFB' }}>
          <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Upload Existing Resume (PDF)</label>
          <input type="file" accept="application/pdf" onChange={e => setFile(e.target.files?.[0] || null)} />
        </div>

        <textarea value={manualDetails} onChange={e => setManualDetails(e.target.value)} placeholder="Or Add/Override Details Manually (Experience, Projects, etc.)" style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', minHeight: '100px' }} />
        <textarea value={jobDescription} onChange={e => setJobDescription(e.target.value)} placeholder="Target Job Description" style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', minHeight: '150px' }} required />
        
        <button type="submit" disabled={isLoading} style={{ padding: '1rem', background: isLoading ? '#9CA3AF' : '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: isLoading ? 'not-allowed' : 'pointer', fontWeight: 'bold' }}>{isLoading ? 'Generating...' : '✨ Generate Tailored Resume'}</button>
      </form>

      {generatedResume && <div style={{ marginTop: '2rem', padding: '1.5rem', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: '8px', whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>{generatedResume}</div>}
    </div>
  );
}