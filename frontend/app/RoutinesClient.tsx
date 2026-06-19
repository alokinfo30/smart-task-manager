'use client';

import React, { useEffect, useState } from 'react';
import { fetchWithAuth } from './fetchWithAuth';

interface Routine {
  id: string;
  name: string;
  start: string;
  end: string;
  days: string[];
}

export default function RoutinesClient() {
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [history, setHistory] = useState<Record<string, any>>({});
  
  const [name, setName] = useState('');
  const [start, setStart] = useState('09:00');
  const [end, setEnd] = useState('10:00');
  const [selectedDays, setSelectedDays] = useState<string[]>(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']);

  const ALL_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const todayStr = new Date().toISOString().split('T')[0];
  const currentDayName = new Date().toLocaleDateString('en-US', { weekday: 'long' });

  const [editRoutineId, setEditRoutineId] = useState<string | null>(null);
  const [editRoutineData, setEditRoutineData] = useState({ name: '', start: '', end: '' });

  const [dailyGoals, setDailyGoals] = useState({
    wakeup: false,
    focus: false,
    exercise: false,
    food: false,
    talk: false
  });

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const [lang, setLang] = useState('English');

  const fetchRoutines = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/routines`);
      const data = await res.json();
      setRoutines(data.settings || []);
      setHistory(data.history || {});
    } catch (err) {
      console.error('Failed to fetch routines', err);
    }
  };

  useEffect(() => {
    fetchRoutines();
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(`dailyGoals_${todayStr}`);
      if (saved) setDailyGoals(JSON.parse(saved));
    }

    const savedLanguage = localStorage.getItem('userLocationLanguage');
    if (savedLanguage) setLang(savedLanguage);

    // Listen for local updates from the AI Agent
    const handleLocalRefresh = () => fetchRoutines();
    window.addEventListener('refresh_data', handleLocalRefresh);
    return () => window.removeEventListener('refresh_data', handleLocalRefresh);
  }, []);

  const speak = (text: string) => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleAddRoutine = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || selectedDays.length === 0) return;
    
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/routines`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, start, end, days: selectedDays })
      });
      setName('');
      fetchRoutines();
    } catch (err) {
      console.error('Failed to add routine', err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/routines/${id}`, { method: 'DELETE' });
      fetchRoutines();
    } catch (err) {
      console.error('Failed to delete routine', err);
    }
  };

  const saveRoutineEdit = async () => {
    if (!editRoutineId) return;
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/routines/edit`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ routine_id: editRoutineId, ...editRoutineData })
      });
      setEditRoutineId(null);
      fetchRoutines();
    } catch (e) { console.error(e); }
  };

  const handleCheck = async (routineId: string, action: 'check_in' | 'check_out') => {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
    const routine = routines.find(r => r.id === routineId);
    
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/routines/check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ routine_id: routineId, action, time, date: todayStr })
      });
      if (routine) {
        speak(`Successfully checked ${action.replace('_', ' ')} for ${routine.name}`);
      }
      fetchRoutines();
    } catch (err) {
      console.error('Failed to check in/out', err);
    }
  };

  const toggleDay = (day: string) => {
    setSelectedDays(prev => prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]);
  };

  const toggleGoal = (key: keyof typeof dailyGoals) => {
    const updated = { ...dailyGoals, [key]: !dailyGoals[key] };
    setDailyGoals(updated);
    if (typeof window !== 'undefined') localStorage.setItem(`dailyGoals_${todayStr}`, JSON.stringify(updated));
  };

  const happinessText = {
    "English": {
      title: "🌱 Happiness System",
      desc: "Remember: the source of your happiness is your lifestyle—talking to good friends, learning something new, eating on time, regular routines, and taking care of yourself. When feeling lonely, ask yourself: 'What do I really need right now? What small action can I take to feel better in 15 minutes?'",
      morning: "🌅 Morning",
      m1: "A glass of water",
      m2: "20 min walk or exercise",
      m3: "Light breakfast",
      m4: "10 min day planning",
      day: "☀️ Day",
      d1: "Full focus on work",
      d2: "Water & stretching every 2-3 hours",
      d3: "Nutritious lunch",
      evening: "🌇 Evening",
      e1: "30 min walk or go outside",
      e2: "Talk to a friend, relative, or colleague for 10-15 mins",
      e3: "Learn something new for 30-60 mins",
      night: "🌙 Night",
      n1: "Light dinner",
      n2: "To-do list for tomorrow",
      n3: "Reduce mobile usage before bed",
      goalTitle: "🎯 A Small 30-Day Goal",
      goalDesc: "Every night, just ensure this:",
      g1: "Woke up on time",
      g2: "Focused on work",
      g3: "Exercised/Walked",
      g4: "Ate healthy food",
      g5: "Talked to someone",
      footer: "Don't pin your happiness on one person. Build it on five pillars: Health, Work/Career, Family, Friends/Social Connection, and Learning/Growth."
    },
    "Hindi": {
      title: "🌱 खुशी मेंटेन करने का सिस्टम (Happiness System)",
      desc: "याद रखें: आपकी खुशी का स्रोत आपकी लाइफस्टाइल है—अच्छे दोस्तों से रोज़ बात करना, कुछ नया सीखना, समय पर खाना, नियमित दिनचर्या और अपने ऊपर ध्यान देना। जब अकेलापन महसूस हो, तो खुद से पूछें: 'अभी मुझे वास्तव में क्या चाहिए? ऐसा कौन सा छोटा काम कर सकता हूँ जिससे 15 मिनट बाद बेहतर महसूस करूँ?'",
      morning: "🌅 सुबह",
      m1: "एक गिलास पानी",
      m2: "20 मिनट वॉक या एक्सरसाइज",
      m3: "हल्का नाश्ता",
      m4: "10 मिनट दिन की योजना",
      day: "☀️ दिन में",
      d1: "काम पर पूरा फोकस",
      d2: "हर 2-3 घंटे में थोड़ा पानी और स्ट्रेचिंग",
      d3: "पौष्टिक लंच",
      evening: "🌇 शाम",
      e1: "30 मिनट वॉक या बाहर निकलना",
      e2: "किसी दोस्त, रिश्तेदार या सहकर्मी से 10-15 मिनट बात करना",
      e3: "30-60 मिनट कुछ नया सीखना",
      night: "🌙 रात",
      n1: "हल्का खाना",
      n2: "अगले दिन की To-do List",
      n3: "सोने से पहले मोबाइल कम इस्तेमाल करना",
      goalTitle: "🎯 एक छोटा 30-दिन का लक्ष्य",
      goalDesc: "रोज़ रात को केवल यह सुनिश्चित करें:",
      g1: "समय पर उठा",
      g2: "काम पर फोकस किया",
      g3: "एक्सरसाइज/वॉक की",
      g4: "हेल्दी खाना खाया",
      g5: "किसी से बात की",
      footer: "अपनी खुशी को किसी एक व्यक्ति पर मत टिकाइए। उसे पाँच स्तंभों पर रखिए: स्वास्थ्य, काम और करियर, परिवार, दोस्त और सामाजिक जुड़ाव, सीखना और व्यक्तिगत विकास।"
    },
    "Spanish": {
      title: "🌱 Sistema de Felicidad",
      desc: "Recuerda: la fuente de tu felicidad es tu estilo de vida: hablar con buenos amigos, aprender algo nuevo, comer a tiempo, tener rutinas regulares y cuidarte. Cuando te sientas solo, pregúntate: '¿Qué necesito realmente ahora mismo? ¿Qué pequeña acción puedo hacer para sentirme mejor en 15 minutos?'",
      morning: "🌅 Mañana",
      m1: "Un vaso de agua",
      m2: "20 min de caminata o ejercicio",
      m3: "Desayuno ligero",
      m4: "10 min planificando el día",
      day: "☀️ Día",
      d1: "Enfoque total en el trabajo",
      d2: "Agua y estiramiento cada 2-3 horas",
      d3: "Almuerzo nutritivo",
      evening: "🌇 Tarde",
      e1: "30 min de caminata o salir al aire libre",
      e2: "Hablar con un amigo, familiar o colega por 10-15 mins",
      e3: "Aprender algo nuevo por 30-60 mins",
      night: "🌙 Noche",
      n1: "Cena ligera",
      n2: "Lista de tareas para mañana",
      n3: "Reducir uso del móvil antes de dormir",
      goalTitle: "🎯 Pequeña Meta de 30 Días",
      goalDesc: "Cada noche, solo asegúrate de esto:",
      g1: "Me desperté a tiempo",
      g2: "Me enfoqué en el trabajo",
      g3: "Hice ejercicio/caminé",
      g4: "Comí saludablemente",
      g5: "Hablé con alguien",
      footer: "No bases tu felicidad en una sola persona. Constrúyela sobre cinco pilares: Salud, Trabajo/Carrera, Familia, Amigos/Conexión Social, y Aprendizaje/Crecimiento."
    }
  };

  const localized = (happinessText as Record<string, any>)[lang] || happinessText["English"];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', alignItems: 'start' }}>
      {/* Left Column: Active Routines for Today */}
      <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <h2 style={{ marginTop: 0, color: '#111827' }}>⏱️ Today's Routines</h2>
        <p style={{ color: '#6B7280', marginBottom: '1.5rem' }}>Active habits for {currentDayName}, {todayStr}</p>
        
        {routines.filter(r => r.days.includes(currentDayName)).length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#9CA3AF', background: '#F9FAFB', borderRadius: '8px' }}>No routines scheduled for today!</div>
        ) : routines.filter(r => r.days.includes(currentDayName)).map(r => {
          const isCheckedIn = !!history[todayStr]?.[r.id]?.check_in;
          const isCheckedOut = !!history[todayStr]?.[r.id]?.check_out;

          return (
            <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: isCheckedOut ? '#D1FAE5' : '#F3F4F6', borderRadius: '8px', marginBottom: '1rem', border: '1px solid #E5E7EB' }}>
              <div>
                <h3 style={{ margin: '0 0 0.25rem 0', color: '#111827' }}>{r.name}</h3>
                <p style={{ margin: 0, fontSize: '0.85rem', color: '#6B7280' }}>Expected: {r.start} - {r.end}</p>
                {isCheckedIn && <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: '#047857', fontWeight: 'bold' }}>In: {history[todayStr][r.id].check_in} {isCheckedOut && `| Out: ${history[todayStr][r.id].check_out}`}</p>}
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {!isCheckedIn && <button onClick={() => handleCheck(r.id, 'check_in')} style={{ padding: '0.5rem 1rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>Check In</button>}
                {isCheckedIn && !isCheckedOut && <button onClick={() => handleCheck(r.id, 'check_out')} style={{ padding: '0.5rem 1rem', background: '#F59E0B', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>Check Out</button>}
              </div>
            </div>
          );
        })}
      </div>

      {/* Right Column: Manage Routines */}
      <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <h2 style={{ marginTop: 0, color: '#111827' }}>⚙️ Manage Routines</h2>
        <form onSubmit={handleAddRoutine} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
          <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Routine Name (e.g. Morning Workout)" style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
          <div style={{ display: 'flex', gap: '1rem' }}>
            <div style={{ flex: 1 }}><label style={{ fontSize: '0.85rem', color: '#6B7280' }}>Start Time</label><input type="time" value={start} onChange={e => setStart(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box' }} required /></div>
            <div style={{ flex: 1 }}><label style={{ fontSize: '0.85rem', color: '#6B7280' }}>End Time</label><input type="time" value={end} onChange={e => setEnd(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box' }} required /></div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {ALL_DAYS.map(day => (
              <button key={day} type="button" onClick={() => toggleDay(day)} style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', fontSize: '0.85rem', cursor: 'pointer', border: '1px solid #D1D5DB', background: selectedDays.includes(day) ? '#10B981' : '#F9FAFB', color: selectedDays.includes(day) ? 'white' : '#374151' }}>
                {day.substring(0, 3)}
              </button>
            ))}
          </div>
          <button type="submit" style={{ padding: '0.75rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>Add Routine</button>
        </form>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {routines.map(r => (
            <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.75rem', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: '4px' }}>
              {editRoutineId === r.id ? (
                <div style={{ display: 'flex', gap: '0.5rem', width: '100%', flexWrap: 'wrap' }}>
                  <input type="text" value={editRoutineData.name} onChange={e => setEditRoutineData({...editRoutineData, name: e.target.value})} style={{ flex: 1, padding: '0.4rem', border: '1px solid #ccc', borderRadius: '4px' }} />
                  <input type="time" value={editRoutineData.start} onChange={e => setEditRoutineData({...editRoutineData, start: e.target.value})} style={{ padding: '0.4rem', border: '1px solid #ccc', borderRadius: '4px' }} />
                  <input type="time" value={editRoutineData.end} onChange={e => setEditRoutineData({...editRoutineData, end: e.target.value})} style={{ padding: '0.4rem', border: '1px solid #ccc', borderRadius: '4px' }} />
                  <button onClick={saveRoutineEdit} style={{ padding: '0.4rem 0.8rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
                  <button onClick={() => setEditRoutineId(null)} style={{ padding: '0.4rem 0.8rem', background: '#9CA3AF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
                </div>
              ) : (
                <>
                  <div><strong style={{ display: 'block', color: '#374151' }}>{r.name}</strong><span style={{ fontSize: '0.75rem', color: '#6B7280' }}>{r.days.map(d => d.substring(0, 3)).join(', ')}</span></div>
                  <div>
                    <button onClick={() => { setEditRoutineId(r.id); setEditRoutineData({ name: r.name, start: r.start, end: r.end }); }} style={{ background: 'none', border: 'none', color: '#F59E0B', cursor: 'pointer', fontSize: '1.2rem', marginRight: '0.5rem' }}>✏️</button>
                    <button onClick={() => handleDelete(r.id)} style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer', fontSize: '1.2rem' }}>×</button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Motivational / Lifestyle Guide */}
      <div style={{ background: '#ECFDF5', padding: '2rem', borderRadius: '8px', border: '1px solid #A7F3D0', gridColumn: '1 / -1', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <h2 style={{ marginTop: 0, color: '#065F46', borderBottom: '2px solid #A7F3D0', paddingBottom: '0.5rem' }}>{localized.title}</h2>
        
        <p style={{ color: '#064E3B', fontSize: '0.95rem', lineHeight: '1.6', marginBottom: '1.5rem' }}>
          {localized.desc}
        </p>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem' }}>
          <div style={{ flex: 1, minWidth: '250px' }}>
            <h3 style={{ color: '#047857', marginTop: 0 }}>{localized.morning}</h3>
            <ul style={{ color: '#064E3B', fontSize: '0.9rem', lineHeight: '1.6', paddingLeft: '1.2rem' }}>
              <li>{localized.m1}</li>
              <li>{localized.m2}</li>
              <li>{localized.m3}</li>
              <li>{localized.m4}</li>
            </ul>

            <h3 style={{ color: '#047857', marginTop: '1.5rem' }}>{localized.day}</h3>
            <ul style={{ color: '#064E3B', fontSize: '0.9rem', lineHeight: '1.6', paddingLeft: '1.2rem' }}>
              <li>{localized.d1}</li>
              <li>{localized.d2}</li>
              <li>{localized.d3}</li>
            </ul>
          </div>

          <div style={{ flex: 1, minWidth: '250px' }}>
            <h3 style={{ color: '#047857', marginTop: 0 }}>{localized.evening}</h3>
            <ul style={{ color: '#064E3B', fontSize: '0.9rem', lineHeight: '1.6', paddingLeft: '1.2rem' }}>
              <li>{localized.e1}</li>
              <li>{localized.e2}</li>
              <li>{localized.e3}</li>
            </ul>

            <h3 style={{ color: '#047857', marginTop: '1.5rem' }}>{localized.night}</h3>
            <ul style={{ color: '#064E3B', fontSize: '0.9rem', lineHeight: '1.6', paddingLeft: '1.2rem' }}>
              <li>{localized.n1}</li>
              <li>{localized.n2}</li>
              <li>{localized.n3}</li>
            </ul>
          </div>
        </div>

        <div style={{ marginTop: '2rem', padding: '1.5rem', background: '#FFFFFF', borderRadius: '8px', borderLeft: '4px solid #10B981' }}>
          <h3 style={{ color: '#111827', marginTop: 0 }}>{localized.goalTitle}</h3>
          <p style={{ color: '#4B5563', fontSize: '0.9rem', marginBottom: '0.5rem' }}>{localized.goalDesc}</p>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', color: '#047857', fontWeight: 'bold', fontSize: '0.9rem', marginBottom: '1rem' }}>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', opacity: dailyGoals.wakeup ? 0.6 : 1, textDecoration: dailyGoals.wakeup ? 'line-through' : 'none' }}><input type="checkbox" checked={dailyGoals.wakeup} onChange={() => toggleGoal('wakeup')} /> {localized.g1}</label>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', opacity: dailyGoals.focus ? 0.6 : 1, textDecoration: dailyGoals.focus ? 'line-through' : 'none' }}><input type="checkbox" checked={dailyGoals.focus} onChange={() => toggleGoal('focus')} /> {localized.g2}</label>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', opacity: dailyGoals.exercise ? 0.6 : 1, textDecoration: dailyGoals.exercise ? 'line-through' : 'none' }}><input type="checkbox" checked={dailyGoals.exercise} onChange={() => toggleGoal('exercise')} /> {localized.g3}</label>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', opacity: dailyGoals.food ? 0.6 : 1, textDecoration: dailyGoals.food ? 'line-through' : 'none' }}><input type="checkbox" checked={dailyGoals.food} onChange={() => toggleGoal('food')} /> {localized.g4}</label>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', opacity: dailyGoals.talk ? 0.6 : 1, textDecoration: dailyGoals.talk ? 'line-through' : 'none' }}><input type="checkbox" checked={dailyGoals.talk} onChange={() => toggleGoal('talk')} /> {localized.g5}</label>
          </div>
          <p style={{ color: '#6B7280', fontSize: '0.85rem', margin: 0, fontStyle: 'italic' }}>
            {localized.footer}
          </p>
        </div>
      </div>
    </div>
  );
}