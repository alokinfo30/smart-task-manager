'use client';

import React, { useState, useRef, useEffect } from 'react';
import { fetchWithAuth } from './fetchWithAuth';
import { useRouter } from 'next/navigation';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function ChatAgent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedMessages, setSelectedMessages] = useState<Set<number>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  
  const [language, setLanguage] = useState('English');
  const [isTTSActive, setIsTTSActive] = useState(false);
  const [isListening, setIsListening] = useState(false);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  // Auto-scroll to the newest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Load persistent chat history on reload
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetchWithAuth(`${API_BASE_URL}/api/chat/history`);
        if (res.ok) {
          const data = await res.json();
          if (data.chat_display) {
            setMessages(data.chat_display.map((m: any) => ({ role: m.role, content: m.content })));
          }
        }
      } catch (e) {
        console.error("Failed to load chat history", e);
      }
    };
    fetchHistory();
  }, []);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;

    const newMessages = [...messages, { role: 'user' as const, content: text }];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    const speak = (text: string) => {
      if (isTTSActive && typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel(); // Stop any ongoing speech
        const utterance = new SpeechSynthesisUtterance(text);
        const langMap: Record<string, string> = {
          "English": "en-US", "Hindi": "hi-IN", "Spanish": "es-ES", "French": "fr-FR",
          "Mandarin": "zh-CN", "Arabic": "ar-SA"
        };
        utterance.lang = langMap[language] || "en-US";
        window.speechSynthesis.speak(utterance);
      }
    };

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, user_id: 'auto', history: messages, language: language })
      });
      const data = await res.json();

      setMessages([...newMessages, { role: 'assistant', content: data.response }]);
      speak(data.response);

      // Tell the Dashboard, Expenses, and Routines to refresh their data locally
      window.dispatchEvent(new CustomEvent('refresh_data'));
      
      // Tell Next.js Server Components to re-fetch data
      router.refresh();
    } catch (error) {
      console.error("Chat failed:", error);
      setMessages([...newMessages, { role: 'assistant', content: "⚠️ Sorry, I encountered an error connecting to the agent." }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Persistent Archiving Logic
  const toggleSelection = (index: number) => {
    const newSet = new Set(selectedMessages);
    if (newSet.has(index)) newSet.delete(index);
    else newSet.add(index);
    setSelectedMessages(newSet);
  };

  const archiveSelected = async () => {
    const contentToArchive = Array.from(selectedMessages).map(i => messages[i].content).join('\n\n');
    if (!contentToArchive) return;
    
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'auto', content: contentToArchive })
      });
      alert("Messages archived successfully!");
      setSelectedMessages(new Set());
    } catch (err) {
      console.error("Archive failed", err);
      alert("Failed to archive messages.");
    }
  };

  const toggleDictation = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice input is not supported in your browser. Please use Chrome or Edge.");
      return;
    }
    
    if (isListening) {
      setIsListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    const langMap: Record<string, string> = {
      "English": "en-US", "Hindi": "hi-IN", "Spanish": "es-ES", "French": "fr-FR",
      "Mandarin": "zh-CN", "Arabic": "ar-SA"
    };
    recognition.lang = langMap[language] || "en-US";
    recognition.start();
    setIsListening(true);
    
    recognition.onresult = (event: any) => setInput(prev => (prev + " " + event.results[0][0].transcript).trim());
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '600px', background: 'white', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ padding: '1rem', borderBottom: '1px solid #E5E7EB', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#F9FAFB', borderRadius: '8px 8px 0 0' }}>
        <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>🤖 AI Agent</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {selectedMessages.size > 0 && (
            <button onClick={archiveSelected} style={{ padding: '0.4rem 0.8rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}>
              💾 Archive ({selectedMessages.size})
            </button>
          )}
        </div>
      </div>

      <div style={{ padding: '0.5rem 1rem', background: '#F3F4F6', borderBottom: '1px solid #E5E7EB', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: '#6B7280', fontWeight: 'bold' }}>🌐 Language:</label>
          <select value={language} onChange={e => setLanguage(e.target.value)} style={{ padding: '0.25rem', border: '1px solid #D1D5DB', borderRadius: '4px', fontSize: '0.85rem' }} disabled={isLoading}>
            <option value="English">English</option><option value="Hindi">Hindi</option><option value="Spanish">Spanish</option><option value="Mandarin">Mandarin</option><option value="Arabic">Arabic</option><option value="French">French</option>
          </select>
        </div>
        <button onClick={() => { setIsTTSActive(!isTTSActive); if (isTTSActive) window.speechSynthesis?.cancel(); }} style={{ padding: '0.25rem 0.5rem', background: isTTSActive ? '#10B981' : '#D1D5DB', color: isTTSActive ? 'white' : '#374151', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}>
          {isTTSActive ? '🔊 Voice ON' : '🔇 Voice OFF'}
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {messages.length === 0 ? (
          <div style={{ margin: 'auto', textAlign: 'center', color: '#6B7280' }}>
            <p>I'm your autonomous assistant. Try asking me:</p>
            <button onClick={() => sendMessage("Analyze my workload")} style={{ margin: '0.5rem', padding: '0.5rem 1rem', borderRadius: '4px', border: '1px solid #D1D5DB', background: 'white', cursor: 'pointer' }}>📊 Analyze Workload</button>
            <button onClick={() => sendMessage("Add a high priority task to review the budget")} style={{ margin: '0.5rem', padding: '0.5rem 1rem', borderRadius: '4px', border: '1px solid #D1D5DB', background: 'white', cursor: 'pointer' }}>➕ Add a Task</button>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} style={{ display: 'flex', gap: '0.5rem', alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
              {msg.role === 'assistant' && <input type="checkbox" checked={selectedMessages.has(idx)} onChange={() => toggleSelection(idx)} style={{ marginTop: '0.8rem', cursor: 'pointer' }} title="Select to archive" />}
              <div style={{ padding: '0.75rem 1rem', borderRadius: '8px', background: msg.role === 'user' ? '#3B82F6' : '#F3F4F6', color: msg.role === 'user' ? 'white' : '#111827', border: msg.role === 'assistant' ? '1px solid #E5E7EB' : 'none', whiteSpace: 'pre-wrap', lineHeight: '1.4' }}>
                {msg.content}
              </div>
            </div>
          ))
        )}
        {isLoading && <div style={{ alignSelf: 'flex-start', background: '#F3F4F6', padding: '0.75rem 1rem', borderRadius: '8px', color: '#6B7280' }}>Agent is thinking...</div>}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ padding: '1rem', borderTop: '1px solid #E5E7EB', background: '#F9FAFB', borderRadius: '0 0 8px 8px' }}>
        <form onSubmit={(e) => { e.preventDefault(); sendMessage(input); }} style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="button" onClick={toggleDictation} style={{ padding: '0.75rem', background: isListening ? '#EF4444' : '#E5E7EB', color: isListening ? 'white' : '#374151', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Voice Input">
            {isListening ? '🛑' : '🎤'}
          </button>
          <input type="text" value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} placeholder="Type a command..." style={{ flex: 1, padding: '0.75rem', borderRadius: '4px', border: '1px solid #D1D5DB' }} disabled={isLoading} autoComplete="off" />
          <button type="submit" disabled={isLoading || !input.trim()} style={{ padding: '0.75rem 1.5rem', background: isLoading || !input.trim() ? '#9CA3AF' : '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: isLoading || !input.trim() ? 'not-allowed' : 'pointer', fontWeight: 'bold' }}>Send</button>
        </form>
      </div>
    </div>
  );
}