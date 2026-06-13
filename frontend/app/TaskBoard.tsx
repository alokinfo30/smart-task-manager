'use client';
import React, { useState } from 'react';
import { useAppStore } from './store';
import { fetchWithAuth } from './fetchWithAuth';
import { useSWRConfig } from 'swr';

export default function TaskBoard({ tasks, fetchTasks, txt, speak, API_BASE_URL, exportToCSV, toggleListenFor, listeningField }: any) {
  const {
    currentUser,
    revealMobiles, setRevealMobiles,
    searchQuery, setSearchQuery,
    newTaskName, setNewTaskName,
    newTaskPriority, setNewTaskPriority,
    editTaskId, setEditTaskId,
    editTaskData, setEditTaskData,
  } = useAppStore();

  const [shareInputs, setShareInputs] = useState<Record<number, string>>({});
  const [revealedTasks, setRevealedTasks] = useState<Record<number, boolean>>({});
  const { mutate } = useSWRConfig();
  const taskKey = currentUser ? `${API_BASE_URL}/api/tasks?user_id=${currentUser}` : null;

  const updateTaskStatus = async (id: number, status: string) => {
    if (taskKey) mutate(taskKey, { tasks: tasks.map((t: any) => t.id === id ? { ...t, status } : t) }, { revalidate: false });
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: id, status, user_id: currentUser })
      });
      if (status === 'Done') speak("Task marked as done");
    } catch (e) { console.error(e); }
    finally { fetchTasks(); }
  };

  const saveTaskEdit = async () => {
    if (editTaskId === null) return;
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks/edit`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: editTaskId, user_id: currentUser, ...editTaskData })
      });
      setEditTaskId(null);
      speak("Task updated");
    } catch (e) { console.error(e); }
    finally { fetchTasks(); }
  };

  const deleteTask = async (id: number) => {
    if (!window.confirm(txt.confirmDeleteTask)) return;
    if (taskKey) mutate(taskKey, { tasks: tasks.filter((t: any) => t.id !== id) }, { revalidate: false });
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks/${id}?user_id=${currentUser}`, { method: "DELETE" });
      speak("Task deleted");
    } catch (e) { console.error(e); }
    finally { fetchTasks(); }
  };

  const clearDoneTasks = async () => {
    if (!window.confirm(txt.confirmClearDone)) return;
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/tasks/done?user_id=${currentUser}`, { method: "DELETE" });
      const data = await res.json();
      if (data.cleared > 0) { speak(`Cleared ${data.cleared} completed tasks`); fetchTasks(); } 
      else { alert("No completed tasks to clear."); }
    } catch (e) { console.error(e); }
  };

  const shareTask = async (taskId: number) => {
    const mobileToShare = shareInputs[taskId];
    if (!mobileToShare) return;
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/tasks/share`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId, shared_with: mobileToShare, user_id: currentUser })
      });
      if (res.ok) { speak("Task shared successfully"); setShareInputs(prev => ({...prev, [taskId]: ""})); } 
      else { const data = await res.json(); alert(data.detail || "Failed to share task"); }
    } catch (e) { console.error(e); }
    finally { fetchTasks(); }
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskName.trim()) return;
    const tempId = Date.now();
    if (taskKey) mutate(taskKey, { tasks: [...tasks, { id: tempId, task: newTaskName, priority: newTaskPriority, status: 'Pending', owner: currentUser }] }, { revalidate: false });
    setNewTaskName("");
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/tasks`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: newTaskName, priority: newTaskPriority, user_id: currentUser })
      });
      speak("Task added successfully");
    } catch (e) { console.error(e); }
    finally { fetchTasks(); }
  };

  const toggleReveal = (id: number) => {
    setRevealedTasks(prev => ({...prev, [id]: !prev[id]}));
  };

  const maskMobile = (m: string, isRevealed: boolean) => {
    if (isRevealed || !m) return m;
    if (m.length <= 4) return "****";
    if (m.includes("@")) { const [u, d] = m.split("@"); return `${u.substring(0, 2)}***@${d}`; }
    return `${m.substring(0, 2)}******${m.substring(m.length - 2)}`;
  };

  const filteredTasks = tasks.filter((t: any) => t.task.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ backgroundColor: '#10B981', color: 'white', padding: '15px', borderRadius: '8px 8px 0 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>{txt.taskBoard}</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={clearDoneTasks} style={{ padding: '5px 10px', backgroundColor: 'white', color: '#10B981', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold' }}>{txt.clearDone}</button>
          <button onClick={() => exportToCSV(tasks, 'tasks.csv')} style={{ padding: '5px 10px', backgroundColor: 'white', color: '#10B981', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold' }}>{txt.exportCsv}</button>
        </div>
      </div>
      <div style={{ height: '30vh', overflowY: 'auto', backgroundColor: '#F9FAFB', padding: '20px', border: '1px solid #E5E7EB', borderTop: 'none' }}>
        <form onSubmit={handleAddTask} style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
          <input type="text" placeholder="Add a new task..." value={newTaskName} onChange={e => setNewTaskName(e.target.value)} style={{ flex: 1, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }} required />
          <button type="button" onClick={() => toggleListenFor('newTaskName')} style={{ padding: '8px 12px', backgroundColor: listeningField === 'newTaskName' ? '#EF4444' : '#E5E7EB', border: 'none', borderRadius: '4px', cursor: 'pointer' }} title="Speech to Text">{listeningField === 'newTaskName' ? '🎙️' : '🎤'}</button>
          <select value={newTaskPriority} onChange={e => setNewTaskPriority(e.target.value)} style={{ padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}>
            <option>High</option><option>Medium</option><option>Low</option>
          </select>
          <button type="submit" style={{ padding: '8px 15px', backgroundColor: '#10B981', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}>Add</button>
        </form>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
          <input type="text" placeholder={txt.searchTasks} value={searchQuery} onChange={e => setSearchQuery(e.target.value)} style={{ flex: 1, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }} />
        </div>
        {filteredTasks.length === 0 ? <p style={{ color: '#6B7280' }}>{txt.noTasks}</p> : filteredTasks.map((task: any) => (
          <div key={task.id} style={{ backgroundColor: 'white', padding: '15px', borderRadius: '8px', border: '1px solid #E5E7EB', marginBottom: '10px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
            {editTaskId === task.id ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                <input type="text" value={editTaskData.task} onChange={e => setEditTaskData({...editTaskData, task: e.target.value})} style={{ padding: '5px', border: '1px solid #ccc', borderRadius: '4px' }} />
                <select value={editTaskData.priority} onChange={e => setEditTaskData({...editTaskData, priority: e.target.value})} style={{ padding: '5px', border: '1px solid #ccc', borderRadius: '4px' }}>
                  <option>High</option><option>Medium</option><option>Low</option>
                </select>
                <div style={{ display: 'flex', gap: '5px' }}>
                  <button onClick={saveTaskEdit} style={{ padding: '5px 10px', backgroundColor: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
                  <button onClick={() => setEditTaskId(null)} style={{ padding: '5px 10px', backgroundColor: '#9CA3AF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
                </div>
              </div>
            ) : (
              <>
                <h3 style={{ margin: '0 0 5px 0' }}>{task.task}</h3>
                <div style={{ display: 'flex', gap: '10px', fontSize: '14px', color: '#4B5563' }}>
                  <span style={{ fontWeight: 'bold', color: task.status === 'Done' ? '#10B981' : '#F59E0B' }}>{task.status}</span>
                  <span>Priority: {task.priority}</span>
                </div>
                <div style={{ marginTop: '10px', display: 'flex', gap: '10px' }}>
                  {task.status !== 'Done' && <button onClick={() => updateTaskStatus(task.id, 'Done')} style={{ padding: '5px 10px', backgroundColor: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>{txt.markDone}</button>}
                  {task.owner === currentUser && <button onClick={() => { setEditTaskId(task.id); setEditTaskData({ task: task.task, priority: task.priority }); }} style={{ padding: '5px 10px', backgroundColor: '#F59E0B', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>Edit</button>}
                  <button onClick={() => deleteTask(task.id)} style={{ padding: '5px 10px', backgroundColor: '#EF4444', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>{txt.delete}</button>
                </div>
                {task.owner === currentUser && (
                  <div style={{ marginTop: '10px', display: 'flex', gap: '5px' }}>
                    <input type="text" placeholder="Share with mobile #" value={shareInputs[task.id] || ''} onChange={e => setShareInputs({...shareInputs, [task.id]: e.target.value})} style={{ padding: '5px', border: '1px solid #ccc', borderRadius: '4px', flex: 1 }} />
                    <button onClick={() => shareTask(task.id)} style={{ padding: '5px 10px', backgroundColor: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>Share</button>
                  </div>
                )}
                {task.shared_with && (
                  <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '5px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                    Shared with: {task.shared_with.split(',').map((s: string) => maskMobile(s.trim(), !!revealedTasks[task.id])).join(', ')}
                    <button onClick={() => toggleReveal(task.id)} style={{ background: 'none', border: 'none', color: '#3B82F6', cursor: 'pointer', fontSize: '12px', textDecoration: 'underline' }}>
                      {revealedTasks[task.id] ? "Hide" : "Reveal"}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}