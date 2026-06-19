'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { fetchWithAuth } from './fetchWithAuth';

interface Expense {
  id: number;
  amount: number | string;
  category: string;
  description: string;
  date: string;
}

export default function ExpenseTrackerClient() {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('Food');
  const [description, setDescription] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);

  const [editExpenseId, setEditExpenseId] = useState<number | null>(null);
  const [editExpenseData, setEditExpenseData] = useState({ amount: 0, category: '', description: '', date: '' });

  const [recurringSettings, setRecurringSettings] = useState<any[]>([]);
  const [recurringHistory, setRecurringHistory] = useState<Record<string, any>>({});
  const [showManageRe, setShowManageRe] = useState(false);
  const [reAmount, setReAmount] = useState('');
  const [reCategory, setReCategory] = useState('Food');
  const [reDesc, setReDesc] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [currency, setCurrency] = useState('USD');
  const [isScanning, setIsScanning] = useState(false);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const fetchExpenses = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/expenses`);
      const data = await res.json();
      setExpenses(data.expenses || []);
    } catch (err) {
      console.error('Failed to fetch expenses', err);
    }
  };

  const fetchRecurring = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/expenses/recurring`);
      const data = await res.json();
      setRecurringSettings(data.settings || []);
      setRecurringHistory(data.history || {});
    } catch(e) {}
  };

  useEffect(() => {
    const savedCurrency = localStorage.getItem('userCurrency');
    if (savedCurrency) setCurrency(savedCurrency);
    fetchExpenses();
    fetchRecurring();

    // Listen for local updates from the AI Agent
    const handleLocalRefresh = () => {
      fetchExpenses();
      fetchRecurring();
    };
    window.addEventListener('refresh_data', handleLocalRefresh);
    return () => window.removeEventListener('refresh_data', handleLocalRefresh);
  }, []);

  const handleAddExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: parseFloat(amount as string),
          category,
          description,
          date
        })
      });
      setAmount('');
      setDescription('');
      fetchExpenses();
    } catch (err) {
      console.error('Failed to add expense', err);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/${id}`, { method: 'DELETE' });
      fetchExpenses();
    } catch (err) {
      console.error('Failed to delete expense', err);
    }
  };

  const handleScanReceipt = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsScanning(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('stm_token='))?.split('=')[1];
      const res = await fetch(`${API_BASE_URL}/api/expenses/scan`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: formData
      });
      if (!res.ok) throw new Error("Scan failed");
      
      const data = await res.json();
      if (data.amount) setAmount(data.amount.toString());
      if (data.category) setCategory(data.category);
      if (data.description) setDescription(data.description);
      if (data.date) setDate(data.date);
      
      alert("Receipt scanned successfully! Please review the details before adding.");
    } catch (err) { console.error(err); alert("Failed to scan receipt. Please enter manually."); }
    finally { setIsScanning(false); }
  };

  const saveExpenseEdit = async () => {
    if (editExpenseId === null) return;
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/edit`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expense_id: editExpenseId, ...editExpenseData })
      });
      setEditExpenseId(null);
      fetchExpenses();
    } catch (e) { console.error(e); }
  };

  const addRecurringExpense = async () => {
    if (!reAmount || !reDesc.trim()) return;
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/recurring`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount: parseFloat(reAmount), category: reCategory, description: reDesc })
      });
      setReAmount(''); setReDesc('');
      fetchRecurring();
    } catch (e) { console.error(e); }
  };

  const handleRecurringCheck = async (exp: any, action: 'added' | 'skipped') => {
    const todayStr = new Date().toISOString().split('T')[0];
    try {
      if (action === 'added') {
        await fetchWithAuth(`${API_BASE_URL}/api/expenses`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount: exp.amount, category: exp.category, description: exp.description, date: todayStr })
        });
      }
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/recurring/check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exp_id: exp.id, action, date: todayStr })
      });
      fetchRecurring();
      fetchExpenses();
    } catch (e) { console.error(e); }
  };

  const deleteRecurring = async (id: string) => {
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/recurring/${id}`, { method: 'DELETE' });
      fetchRecurring();
    } catch(e) {}
  };

  const dailyTotal = useMemo(() => {
    const today = new Date().toISOString().split('T')[0];
    return expenses.filter(e => e.date === today).reduce((sum, e) => sum + Number(e.amount), 0);
  }, [expenses]);

  const monthlyTotal = useMemo(() => {
    const currentMonth = new Date().toISOString().slice(0, 7);
    return expenses.filter(e => e.date.startsWith(currentMonth)).reduce((sum, e) => sum + Number(e.amount), 0);
  }, [expenses]);

  const chartData = useMemo(() => {
    const data = [];
    for (let i = 29; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      const total = expenses
        .filter(e => e.date === dateStr)
        .reduce((sum, exp) => sum + (Number(exp.amount) || 0), 0);
      data.push({ date: dateStr.substring(5), amount: total });
    }
    return data;
  }, [expenses]);

  const exportToCSV = () => {
    const headers = ['Date', 'Description', 'Category', 'Amount'];
    const csvData = expenses.map(e => [e.date, `"${e.description}"`, e.category, e.amount].join(','));
    const blob = new Blob([headers.join(','), '\n', csvData.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'expenses.csv';
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
    
    recognition.onresult = (event: any) => setDescription(prev => (prev + " " + event.results[0][0].transcript).trim());
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
  };

  return (
    <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
        <button onClick={exportToCSV} style={{ padding: '0.5rem 1rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>📥 Export CSV</button>
      </div>
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ flex: 1, padding: '1.5rem', background: '#FEF3C7', borderRadius: '8px', textAlign: 'center', border: '1px solid #FDE68A' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#D97706' }}>Daily Total</h3>
          <p style={{ margin: 0, fontSize: '2rem', fontWeight: 'bold', color: '#92400E' }}>{currency} {dailyTotal.toFixed(2)}</p>
        </div>
        <div style={{ flex: 1, padding: '1.5rem', background: '#DBEAFE', borderRadius: '8px', textAlign: 'center', border: '1px solid #BFDBFE' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#1D4ED8' }}>Monthly Total</h3>
          <p style={{ margin: 0, fontSize: '2rem', fontWeight: 'bold', color: '#1E3A8A' }}>{currency} {monthlyTotal.toFixed(2)}</p>
        </div>
      </div>

      <div style={{ marginBottom: '2rem', padding: '1.5rem', background: 'white', border: '1px solid #E5E7EB', borderRadius: '8px', height: '300px' }}>
        <h4 style={{ margin: '0 0 1rem 0', color: '#4B5563' }}>📈 30-Day Trend</h4>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} tickFormatter={(val) => `${currency} ${val}`} width={60} />
            <Tooltip formatter={(value: number) => [`${currency} ${value.toFixed(2)}`, 'Spent']} labelStyle={{ color: 'black' }} />
            <Line type="monotone" dataKey="amount" stroke="#EF4444" strokeWidth={3} dot={{ r: 3, fill: '#EF4444' }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div style={{ marginBottom: '2rem', padding: '1.5rem', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0, color: '#374151' }}>Recurring Expenses</h3>
          <button onClick={() => setShowManageRe(!showManageRe)} style={{ padding: '0.5rem 1rem', background: '#E5E7EB', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', color: '#4B5563' }}>{showManageRe ? 'Hide Manage' : 'Manage Recurring'}</button>
        </div>
        
        {showManageRe && (
          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
              <input type="number" value={reAmount} onChange={e => setReAmount(e.target.value)} placeholder="Amount" style={{ flex: 1, padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px', minWidth: '80px' }} />
              <select value={reCategory} onChange={e => setReCategory(e.target.value)} style={{ flex: 1, padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}>
                <option>Food</option><option>Transport</option><option>Shopping</option><option>Bills</option><option>Other</option>
              </select>
              <input type="text" value={reDesc} onChange={e => setReDesc(e.target.value)} placeholder="Description" style={{ flex: 2, padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px', minWidth: '150px' }} />
              <button onClick={addRecurringExpense} style={{ padding: '0.5rem 1rem', background: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Add</button>
            </div>
            {recurringSettings.map(r => (
              <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid #E5E7EB', fontSize: '0.9rem' }}>
                <span>{r.description} - ${r.amount} ({r.category})</span>
                <button onClick={() => deleteRecurring(r.id)} style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer' }}>🗑️</button>
              </div>
            ))}
          </div>
        )}

        {recurringSettings.filter((r: any) => !(recurringHistory[new Date().toISOString().split('T')[0]]?.[r.id])).map((r: any) => (
          <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', backgroundColor: '#FEF3C7', border: '1px solid #FDE68A', borderRadius: '8px', marginBottom: '0.5rem' }}>
            <span><strong>{r.description}</strong> - {currency} {r.amount} ({r.category})</span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button onClick={() => handleRecurringCheck(r, 'added')} style={{ padding: '0.4rem 0.8rem', backgroundColor: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>Add Today</button>
              <button onClick={() => handleRecurringCheck(r, 'skipped')} style={{ padding: '0.4rem 0.8rem', backgroundColor: '#9CA3AF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>Skip</button>
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={handleAddExpense} style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
        <input type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} placeholder={`Amount (${currency})`} style={{ flex: 1, padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', minWidth: '100px' }} required />
        <select value={category} onChange={e => setCategory(e.target.value)} style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }}>
          <option value="Food">Food</option>
          <option value="Transport">Transport</option>
          <option value="Shopping">Shopping</option>
          <option value="Bills">Bills</option>
          <option value="Other">Other</option>
        </select>
        <label style={{ padding: '0.75rem 1rem', background: isScanning ? '#9CA3AF' : '#8B5CF6', color: 'white', border: 'none', borderRadius: '4px', cursor: isScanning ? 'not-allowed' : 'pointer', fontWeight: 'bold', display: 'flex', alignItems: 'center' }}>
          {isScanning ? '⏳ Scanning...' : '📷 Scan Receipt'}
          <input type="file" accept="image/*" onChange={handleScanReceipt} style={{ display: 'none' }} disabled={isScanning} />
        </label>
        <button type="button" onClick={toggleDictation} style={{ padding: '0.75rem', background: isListening ? '#EF4444' : '#E5E7EB', color: isListening ? 'white' : '#374151', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Voice Dictation">
          {isListening ? '🛑' : '🎤'}
        </button>
        <input type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder="Description..." style={{ flex: 2, padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px', minWidth: '200px' }} required />
        <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        <button type="submit" style={{ padding: '0.75rem 1.5rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>Add Expense</button>
      </form>

      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #E5E7EB', color: '#6B7280' }}>
            <th style={{ padding: '0.75rem' }}>Date</th>
            <th style={{ padding: '0.75rem' }}>Description</th>
            <th style={{ padding: '0.75rem' }}>Category</th>
            <th style={{ padding: '0.75rem' }}>Amount</th>
            <th style={{ padding: '0.75rem', width: '50px' }}></th>
          </tr>
        </thead>
        <tbody>
          {expenses.length === 0 ? (
            <tr><td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: '#9CA3AF' }}>No expenses logged yet.</td></tr>
          ) : (
            expenses.map(exp => (
              <tr key={exp.id} style={{ borderBottom: '1px solid #F3F4F6' }}>
                {editExpenseId === exp.id ? (
                  <td colSpan={5} style={{ padding: '0.75rem' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <input type="date" value={editExpenseData.date} onChange={e => setEditExpenseData({...editExpenseData, date: e.target.value})} style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }} />
                      <input type="text" value={editExpenseData.description} onChange={e => setEditExpenseData({...editExpenseData, description: e.target.value})} style={{ flex: 1, padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }} />
                      <input type="text" value={editExpenseData.category} onChange={e => setEditExpenseData({...editExpenseData, category: e.target.value})} style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px', width: '100px' }} />
                      <input type="number" value={editExpenseData.amount} onChange={e => setEditExpenseData({...editExpenseData, amount: parseFloat(e.target.value) || 0})} style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px', width: '80px' }} />
                      <button onClick={saveExpenseEdit} style={{ padding: '0.5rem 1rem', backgroundColor: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
                      <button onClick={() => setEditExpenseId(null)} style={{ padding: '0.5rem 1rem', backgroundColor: '#9CA3AF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
                    </div>
                  </td>
                ) : (
                  <>
                <td style={{ padding: '0.75rem', color: '#6B7280' }}>{exp.date}</td>
                <td style={{ padding: '0.75rem', fontWeight: '500', color: '#111827' }}>{exp.description}</td>
                <td style={{ padding: '0.75rem' }}>
                  <span style={{ background: '#F3F4F6', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.85rem' }}>{exp.category}</span>
                </td>
                <td style={{ padding: '0.75rem', fontWeight: 'bold', color: '#EF4444' }}>{currency} {Number(exp.amount).toFixed(2)}</td>
                <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                  <button onClick={() => { setEditExpenseId(exp.id); setEditExpenseData({ amount: Number(exp.amount), category: exp.category, description: exp.description, date: exp.date }); }} style={{ background: 'none', border: 'none', color: '#F59E0B', cursor: 'pointer', fontSize: '1.2rem', marginRight: '0.5rem' }}>✏️</button>
                  <button onClick={() => handleDelete(exp.id)} style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer', fontSize: '1.2rem' }}>×</button>
                </td>
                  </>
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}