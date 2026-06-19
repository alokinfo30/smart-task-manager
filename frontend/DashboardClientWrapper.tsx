'use client';

import React, { useEffect, useState, useRef } from 'react';
import Pusher from 'pusher-js';
import { fetchWithAuth } from './app/fetchWithAuth';
import { useAppDispatch, useAppSelector } from './hooks';
import { setTasks, setNewTaskText, setNewTaskPriority, setEditTaskId, setEditTaskData, setShareInput, toggleRevealedTask, setSearchQuery, setIsListening, appendNewTaskText } from './dashboardSlice';

interface Task {
  id: number;
  date: string;
  task: string;
  status: string;
  priority: string;
  completed_at: string;
  owner: string;
  shared_with: string;
  comment?: string;
}

export default function DashboardClientWrapper({ session }: { session: string }) {
  const dispatch = useAppDispatch();
  const { tasks, newTaskText, newTaskPriority, editTaskId, editTaskData, shareInputs, revealedTasks, searchQuery, isListening } = useAppSelector((state) => state.dashboard);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const [pomoTime, setPomoTime] = useState(25 * 60);
  const [isPomoActive, setIsPomoActive] = useState(false);
  const [customPomoMinutes, setCustomPomoMinutes] = useState(25);

  // Load custom Pomodoro time preference from storage
  useEffect(() => {
    const savedPomo = localStorage.getItem('userPomoMinutes');
    if (savedPomo) {
      setCustomPomoMinutes(parseInt(savedPomo, 10));
      setPomoTime(parseInt(savedPomo, 10) * 60);
    }
  }, []);

  // Fetch location for Currency & Happiness System Language
  useEffect(() => {
    fetch('https://ipapi.co/json/')
      .then(res => res.json())
      .then(data => {
        if (data.currency) localStorage.setItem('userCurrency', data.currency);
        const country = data.country_code;
        let lang = 'English';
        if (['ES', 'MX', 'AR'].includes(country)) lang = 'Spanish';
        else if (country === 'IN') lang = 'Hindi';
        else if (country === 'FR') lang = 'French';
        localStorage.setItem('userLocationLanguage', lang);
      })
      .catch(() => console.error("Failed to fetch location"));
  }, []);

  // Pomodoro Timer Logic
  useEffect(() => {
    let interval: any;
    if (isPomoActive && pomoTime > 0) {
      interval = setInterval(() => setPomoTime(t => t - 1), 1000);
    } else if (pomoTime === 0 && isPomoActive) {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.speak(new SpeechSynthesisUtterance("Focus session complete! Great job, take a short break."));
      }
      
      setIsPomoActive(false);
      setPomoTime(customPomoMinutes * 60);
    }
    return () => clearInterval(interval);
  }, [isPomoActive, pomoTime, customPomoMinutes]);

  // Fetch tasks from the FastAPI backend
  const fetchTasks = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/tasks`);
      if (res.ok) {
        const data = await res.json();
        dispatch(setTasks(data.tasks || []));
      }
    } catch (error) {
      console.error("Failed to fetch tasks", error);
    }
  };

  useEffect(() => {
    fetchTasks();

    // Local synchronization (when Pusher is not configured)
    const handleLocalRefresh = () => fetchTasks();
    window.addEventListener('refresh_data', handleLocalRefresh);

    // Real-time synchronization using Pusher
    const pusherKey = process.env.NEXT_PUBLIC_PUSHER_KEY;
    const pusherCluster = process.env.NEXT_PUBLIC_PUSHER_CLUSTER;
    
    let channel: any;
    if (pusherKey && pusherCluster) {
      const pusher = new Pusher(pusherKey, { cluster: pusherCluster });
      channel = pusher.subscribe('task-board');
      
      channel.bind('update', () => {
        fetchTasks(); // Refresh board automatically when AI or others update tasks!
      });
    }

    return () => {
      window.removeEventListener('refresh_data', handleLocalRefresh);
      if (channel) {
        channel.unbind_all();
        channel.unsubscribe();
      }
    };
  }, []);

  // Handle Adding a Task
  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskText) return;
    
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: newTaskText,
          priority: newTaskPriority,
          date: new Date().toISOString().split('T')[0],
          shared_with: ""
        })
      });
    dispatch(setNewTaskText(''));
      fetchTasks(); // Refresh the board
    } catch (error) {
      console.error("Failed to add task", error);
    }
  };

  // Handle Status Updates (Moving between columns)
  const updateStatus = async (taskId: number, newStatus: string) => {
    const reason = window.prompt(`Moving to ${newStatus}. Add a reason/status update in detail:`);
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, status: newStatus, comment: reason || "" })
      });
      if (newStatus === 'Working') {
        setIsPomoActive(true);
        if (pomoTime === 0 || !isPomoActive) {
          setPomoTime(customPomoMinutes * 60);
        }
      } else if (newStatus === 'Pending' || newStatus === 'Done') {
        setIsPomoActive(false);
      }
      fetchTasks(); // Refresh the board
    } catch (error) {
      console.error("Failed to update status", error);
    }
  };

  // Handle Task Deletion
  const deleteTask = async (taskId: number) => {
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks/${taskId}`, { method: 'DELETE' });
      fetchTasks(); // Refresh the board
    } catch (error) {
      console.error("Failed to delete task", error);
    }
  };

  const saveTaskEdit = async () => {
    if (editTaskId === null) return;
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks/edit`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: editTaskId, task: editTaskData.task, priority: editTaskData.priority, comment: editTaskData.comment })
      });
    dispatch(setEditTaskId(null));
      fetchTasks();
    } catch (e) { console.error(e); }
  };

  const clearDoneTasks = async () => {
    if (!window.confirm("Clear all completed tasks?")) return;
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks/done`, { method: 'DELETE' });
      fetchTasks();
    } catch (e) { console.error(e); }
  };

  const shareTask = async (taskId: number) => {
    let mobile = shareInputs[taskId];
    if (!mobile) return;

    // Auto-clean mobile numbers (Leave emails untouched)
    if (!mobile.includes('@')) {
      mobile = mobile.replace(/\D/g, '');
      if (mobile.length !== 10) {
        alert("Mobile number must be exactly 10 digits.");
        return;
      }
    }

    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/tasks/share`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, shared_with: mobile })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to share task");
      }
    dispatch(setShareInput({ id: taskId, value: '' }));
      fetchTasks();
    } catch (e: any) { alert(e.message || "Failed to share task"); }
  };

  const exportToCSV = () => {
    const headers = ['ID', 'Task', 'Priority', 'Status', 'Date', 'Completed At'];
    const csvData = tasks.map(t => [t.id, `"${t.task}"`, t.priority, t.status, t.date, t.completed_at].join(','));
    const blob = new Blob([headers.join(','), '\n', csvData.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'tasks.csv';
    a.click();
  };

  const toggleDictation = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return alert("Voice input not supported in your browser.");
    
    if (isListening) {
      dispatch(setIsListening(false));
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.start();
    dispatch(setIsListening(true));
    
    recognition.onresult = (event: any) => dispatch(appendNewTaskText(event.results[0][0].transcript));
    recognition.onend = () => dispatch(setIsListening(false));
    recognition.onerror = () => dispatch(setIsListening(false));
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const filteredTasks = tasks.filter(t => t.task.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div>
      {/* Add Task Form */}
      <div style={{ background: 'white', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>➕ Add New Task</h2>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button onClick={clearDoneTasks} style={{ padding: '0.5rem 1rem', background: '#EF4444', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold' }}>🧹 Clear Done Tasks</button>
            <button onClick={exportToCSV} style={{ padding: '0.5rem 1rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold' }}>📥 Export CSV</button>
          </div>
        </div>
        <form onSubmit={handleAddTask} style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
          <button type="button" onClick={toggleDictation} style={{ padding: '0.75rem', background: isListening ? '#EF4444' : '#E5E7EB', color: isListening ? 'white' : '#374151', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Voice Dictation">
            {isListening ? '🛑' : '🎤'}
          </button>
        <input type="text" value={newTaskText} onChange={(e) => dispatch(setNewTaskText(e.target.value))} placeholder="E.g., Review monthly budget..." style={{ flex: 1, padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        <select value={newTaskPriority} onChange={(e) => dispatch(setNewTaskPriority(e.target.value))} style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }}>
            <option value="High">High Priority</option>
            <option value="Medium">Medium Priority</option>
            <option value="Low">Low Priority</option>
          </select>
          <button type="submit" style={{ padding: '0.75rem 1.5rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>Add Task</button>
        </form>
      </div>

      {/* Search Tasks */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <input type="text" placeholder="🔍 Search tasks..." value={searchQuery} onChange={e => dispatch(setSearchQuery(e.target.value))} style={{ flex: 1, padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box', minWidth: '200px' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', background: isPomoActive ? '#FEF2F2' : '#F3F4F6', padding: '0.5rem 1rem', borderRadius: '8px', border: `1px solid ${isPomoActive ? '#FCA5A5' : '#D1D5DB'}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontWeight: 'bold', color: '#374151', fontSize: '0.9rem' }}>🍅 Mins:</span>
            <input type="number" min="1" max="120" value={customPomoMinutes} onChange={e => {
              const val = parseInt(e.target.value) || 25;
              setCustomPomoMinutes(val);
              localStorage.setItem('userPomoMinutes', val.toString());
              if (!isPomoActive) setPomoTime(val * 60);
            }} disabled={isPomoActive} style={{ width: '60px', padding: '0.25rem', borderRadius: '4px', border: '1px solid #D1D5DB' }} />
          </div>
          <span style={{ fontWeight: 'bold', color: isPomoActive ? '#B91C1C' : '#374151', fontSize: '1.2rem', fontFamily: 'monospace' }}>{formatTime(pomoTime)}</span>
          <button onClick={() => setIsPomoActive(!isPomoActive)} style={{ padding: '0.4rem 0.8rem', background: isPomoActive ? '#EF4444' : '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>{isPomoActive ? 'Pause' : 'Start Focus'}</button>
          <button onClick={() => { setIsPomoActive(false); setPomoTime(customPomoMinutes * 60); }} style={{ padding: '0.4rem 0.8rem', background: '#6B7280', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Reset</button>
        </div>
      </div>

      {/* Kanban Board */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
        {['Pending', 'Working', 'Done'].map(statusGroup => (
          <div key={statusGroup} style={{ background: '#F3F4F6', padding: '1rem', borderRadius: '8px', border: '1px solid #E5E7EB' }}>
            <h3 style={{ marginTop: 0, borderBottom: '2px solid #E5E7EB', paddingBottom: '0.5rem', color: '#374151' }}>{statusGroup}</h3>
            
            {filteredTasks.filter(t => t.status === statusGroup).map(task => (
              <div key={task.id} style={{ background: 'white', padding: '1rem', borderRadius: '6px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)', marginBottom: '1rem', borderLeft: `4px solid ${task.priority === 'High' ? '#EF4444' : task.priority === 'Medium' ? '#F59E0B' : '#10B981'}` }}>
                {editTaskId === task.id ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <input type="text" value={editTaskData.task} onChange={e => dispatch(setEditTaskData({...editTaskData, task: e.target.value}))} style={{ padding: '0.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} />
                <textarea value={editTaskData.comment} onChange={e => dispatch(setEditTaskData({...editTaskData, comment: e.target.value}))} placeholder="Add a comment or detail status reason..." style={{ padding: '0.5rem', border: '1px solid #D1D5DB', borderRadius: '4px', resize: 'none' }} />
                <select value={editTaskData.priority} onChange={e => dispatch(setEditTaskData({...editTaskData, priority: e.target.value}))} style={{ padding: '0.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }}>
                      <option>High</option><option>Medium</option><option>Low</option>
                    </select>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button onClick={saveTaskEdit} style={{ padding: '0.25rem 0.5rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>Save</button>
                  <button onClick={() => dispatch(setEditTaskId(null))} style={{ padding: '0.25rem 0.5rem', background: '#9CA3AF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p style={{ margin: '0 0 0.25rem 0', fontWeight: 'bold', color: '#111827' }}>{task.task}</p>
                    {task.comment && <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#6B7280', fontStyle: 'italic' }}>💬 {task.comment}</p>}
                  </>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#6B7280', marginBottom: '1rem' }}>
                  <span>{task.priority}</span><span>{task.date}</span>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {statusGroup !== 'Pending' && <button onClick={() => updateStatus(task.id, 'Pending')} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #D1D5DB', background: 'white' }}>← Pending</button>}
                  {statusGroup !== 'Working' && <button onClick={() => updateStatus(task.id, 'Working')} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #D1D5DB', background: '#DBEAFE', color: '#1D4ED8' }}>{statusGroup === 'Pending' ? 'Start Working →' : '← Working'}</button>}
                  {statusGroup !== 'Done' && <button onClick={() => updateStatus(task.id, 'Done')} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #D1D5DB', background: '#D1FAE5', color: '#047857' }}>Done ✓</button>}
              {task.owner === session && editTaskId !== task.id && <button onClick={() => { dispatch(setEditTaskId(task.id)); dispatch(setEditTaskData({ task: task.task, priority: task.priority, comment: task.comment || '' })); }} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', color: '#F59E0B', background: 'transparent', border: 'none' }}>✏️</button>}
                  <button onClick={() => deleteTask(task.id)} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', color: '#EF4444', marginLeft: 'auto', background: 'transparent', border: 'none' }}>🗑️</button>
                </div>
                {task.owner === session && (
                  <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
                <input type="text" placeholder="Share with mobile #" value={shareInputs[task.id] || ''} onChange={e => dispatch(setShareInput({ id: task.id, value: e.target.value }))} style={{ padding: '0.4rem', border: '1px solid #D1D5DB', borderRadius: '4px', flex: 1, fontSize: '0.8rem' }} />
                    <button onClick={() => shareTask(task.id)} style={{ padding: '0.4rem 0.75rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>Share</button>
                  </div>
                )}
                {task.shared_with && (
                  <div style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.5rem' }}>
                    Shared: {task.shared_with.split(',').map((s: string) => revealedTasks[task.id] ? s.trim() : s.trim().substring(0, 2) + '******' + s.trim().slice(-2)).join(', ')}
                <button onClick={() => dispatch(toggleRevealedTask(task.id))} style={{ background: 'none', border: 'none', color: '#3B82F6', cursor: 'pointer', marginLeft: '0.5rem' }}>{revealedTasks[task.id] ? 'Hide' : 'Reveal'}</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}