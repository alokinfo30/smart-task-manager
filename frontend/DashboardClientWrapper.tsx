'use client';

import React, { useEffect, useState } from 'react';
import Pusher from 'pusher-js';
import { fetchWithAuth } from './app/fetchWithAuth';

interface Task {
  id: number;
  date: string;
  task: string;
  status: string;
  priority: string;
  completed_at: string;
  owner: string;
  shared_with: string;
}

export default function DashboardClientWrapper({ session }: { session: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [newTaskText, setNewTaskText] = useState('');
  const [newTaskPriority, setNewTaskPriority] = useState('High');
  const [editTaskId, setEditTaskId] = useState<number | null>(null);
  const [editTaskData, setEditTaskData] = useState({ task: '', priority: 'Medium' });
  const [shareInputs, setShareInputs] = useState<Record<number, string>>({});
  const [revealedTasks, setRevealedTasks] = useState<Record<number, boolean>>({});
  const [searchQuery, setSearchQuery] = useState('');
  const [isListening, setIsListening] = useState(false);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  // Fetch tasks from the FastAPI backend
  const fetchTasks = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/tasks`);
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || []);
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
      setNewTaskText('');
      fetchTasks(); // Refresh the board
    } catch (error) {
      console.error("Failed to add task", error);
    }
  };

  // Handle Status Updates (Moving between columns)
  const updateStatus = async (taskId: number, newStatus: string) => {
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, status: newStatus })
      });
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
        body: JSON.stringify({ task_id: editTaskId, task: editTaskData.task, priority: editTaskData.priority })
      });
      setEditTaskId(null);
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
    const mobile = shareInputs[taskId];
    if (!mobile) return;
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
      setShareInputs(prev => ({ ...prev, [taskId]: '' }));
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
      setIsListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.start();
    setIsListening(true);
    
    recognition.onresult = (event: any) => setNewTaskText(prev => (prev + " " + event.results[0][0].transcript).trim());
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
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
          <input type="text" value={newTaskText} onChange={(e) => setNewTaskText(e.target.value)} placeholder="E.g., Review monthly budget..." style={{ flex: 1, padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
          <select value={newTaskPriority} onChange={(e) => setNewTaskPriority(e.target.value)} style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }}>
            <option value="High">High Priority</option>
            <option value="Medium">Medium Priority</option>
            <option value="Low">Low Priority</option>
          </select>
          <button type="submit" style={{ padding: '0.75rem 1.5rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>Add Task</button>
        </form>
      </div>

      {/* Search Tasks */}
      <div style={{ marginBottom: '1.5rem' }}>
        <input type="text" placeholder="🔍 Search tasks..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} style={{ width: '100%', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', boxSizing: 'border-box' }} />
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
                    <input type="text" value={editTaskData.task} onChange={e => setEditTaskData({...editTaskData, task: e.target.value})} style={{ padding: '0.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} />
                    <select value={editTaskData.priority} onChange={e => setEditTaskData({...editTaskData, priority: e.target.value})} style={{ padding: '0.5rem', border: '1px solid #D1D5DB', borderRadius: '4px' }}>
                      <option>High</option><option>Medium</option><option>Low</option>
                    </select>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button onClick={saveTaskEdit} style={{ padding: '0.25rem 0.5rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>Save</button>
                      <button onClick={() => setEditTaskId(null)} style={{ padding: '0.25rem 0.5rem', background: '#9CA3AF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <p style={{ margin: '0 0 0.5rem 0', fontWeight: 'bold', color: '#111827' }}>{task.task}</p>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#6B7280', marginBottom: '1rem' }}>
                  <span>{task.priority}</span><span>{task.date}</span>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {statusGroup !== 'Pending' && <button onClick={() => updateStatus(task.id, 'Pending')} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #D1D5DB', background: 'white' }}>← Pending</button>}
                  {statusGroup !== 'Working' && <button onClick={() => updateStatus(task.id, 'Working')} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #D1D5DB', background: '#DBEAFE', color: '#1D4ED8' }}>{statusGroup === 'Pending' ? 'Start Working →' : '← Working'}</button>}
                  {statusGroup !== 'Done' && <button onClick={() => updateStatus(task.id, 'Done')} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #D1D5DB', background: '#D1FAE5', color: '#047857' }}>Done ✓</button>}
                  {task.owner === session && editTaskId !== task.id && <button onClick={() => { setEditTaskId(task.id); setEditTaskData({ task: task.task, priority: task.priority }); }} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', color: '#F59E0B', background: 'transparent', border: 'none' }}>✏️</button>}
                  <button onClick={() => deleteTask(task.id)} style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', color: '#EF4444', marginLeft: 'auto', background: 'transparent', border: 'none' }}>🗑️</button>
                </div>
                {task.owner === session && (
                  <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
                    <input type="text" placeholder="Share with mobile #" value={shareInputs[task.id] || ''} onChange={e => setShareInputs({...shareInputs, [task.id]: e.target.value})} style={{ padding: '0.4rem', border: '1px solid #D1D5DB', borderRadius: '4px', flex: 1, fontSize: '0.8rem' }} />
                    <button onClick={() => shareTask(task.id)} style={{ padding: '0.4rem 0.75rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>Share</button>
                  </div>
                )}
                {task.shared_with && (
                  <div style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.5rem' }}>
                    Shared: {task.shared_with.split(',').map((s: string) => revealedTasks[task.id] ? s.trim() : s.trim().substring(0, 2) + '******' + s.trim().slice(-2)).join(', ')}
                    <button onClick={() => setRevealedTasks(prev => ({ ...prev, [task.id]: !prev[task.id] }))} style={{ background: 'none', border: 'none', color: '#3B82F6', cursor: 'pointer', marginLeft: '0.5rem' }}>{revealedTasks[task.id] ? 'Hide' : 'Reveal'}</button>
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