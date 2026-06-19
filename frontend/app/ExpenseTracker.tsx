'use client';

import React, { useState, useEffect } from 'react';
import { fetchWithAuth } from './fetchWithAuth';

interface Expense {
  id: number;
  date: string;
  amount: number;
  category: string;
  description: string;
}

export default function ExpenseTracker() {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [currency, setCurrency] = useState('USD');
  
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('Food');
  const [description, setDescription] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const fetchExpenses = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/expenses`);
      if (res.ok) {
        const data = await res.json();
        setExpenses(data.expenses || []);
      }
    } catch (e) { console.error("Failed to fetch expenses", e); }
  };

  useEffect(() => {
    // Load the dynamic location-based currency set by the Dashboard
    const savedCurrency = localStorage.getItem('userCurrency');
    if (savedCurrency) setCurrency(savedCurrency);
    
    fetchExpenses();
  }, []);

  const handleAddExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!amount || isNaN(Number(amount)) || Number(amount) <= 0) return alert("Enter a valid amount");

    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount: Number(amount), category, description, date })
      });
      setAmount('');
      setDescription('');
      fetchExpenses();
    } catch (e) {
      console.error("Failed to add expense", e);
    }
  };

  const deleteExpense = async (id: number) => {
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/${id}`, { method: 'DELETE' });
      fetchExpenses();
    } catch (e) { console.error(e); }
  };

  const dailyTotal = expenses.filter(e => e.date === new Date().toISOString().split('T')[0]).reduce((sum, e) => sum + e.amount, 0);
  const monthlyTotal = expenses.filter(e => e.date.startsWith(new Date().toISOString().slice(0, 7))).reduce((sum, e) => sum + e.amount, 0);

  return (
    <div style={{ padding: '2rem', background: 'white', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <h2 style={{ marginTop: 0 }}>💰 Expense Tracker</h2>
      
      <div style={{ display: 'flex', gap: '2rem', marginBottom: '2rem' }}>
        <div style={{ padding: '1.5rem', background: '#F3F4F6', borderRadius: '8px', flex: 1, textAlign: 'center' }}>
          <p style={{ margin: '0 0 0.5rem 0', color: '#6B7280', fontWeight: 'bold' }}>Daily Total</p>
          <h3 style={{ margin: 0, fontSize: '1.8rem', color: '#111827' }}>{currency} {dailyTotal.toFixed(2)}</h3>
        </div>
        <div style={{ padding: '1.5rem', background: '#F3F4F6', borderRadius: '8px', flex: 1, textAlign: 'center' }}>
          <p style={{ margin: '0 0 0.5rem 0', color: '#6B7280', fontWeight: 'bold' }}>Monthly Total</p>
          <h3 style={{ margin: 0, fontSize: '1.8rem', color: '#111827' }}>{currency} {monthlyTotal.toFixed(2)}</h3>
        </div>
      </div>

      <form onSubmit={handleAddExpense} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
        <input type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} placeholder={`Amount (${currency})`} style={{ flex: 1, minWidth: '100px', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        <select value={category} onChange={e => setCategory(e.target.value)} style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }}>
          <option>Food</option><option>Transport</option><option>Shopping</option><option>Bills</option><option>Other</option>
        </select>
        <input type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder="Description" style={{ flex: 2, minWidth: '200px', padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ padding: '0.75rem', border: '1px solid #D1D5DB', borderRadius: '4px' }} required />
        <button type="submit" style={{ padding: '0.75rem 1.5rem', background: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>➕ Add</button>
      </form>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#F9FAFB', borderBottom: '2px solid #E5E7EB', textAlign: 'left' }}>
            <th style={{ padding: '0.75rem' }}>Date</th>
            <th style={{ padding: '0.75rem' }}>Category</th>
            <th style={{ padding: '0.75rem' }}>Description</th>
            <th style={{ padding: '0.75rem' }}>Amount</th>
            <th style={{ padding: '0.75rem' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {expenses.map(exp => (
            <tr key={exp.id} style={{ borderBottom: '1px solid #E5E7EB' }}>
              <td style={{ padding: '0.75rem' }}>{exp.date}</td>
              <td style={{ padding: '0.75rem' }}>{exp.category}</td>
              <td style={{ padding: '0.75rem' }}>{exp.description}</td>
              <td style={{ padding: '0.75rem', fontWeight: 'bold' }}>{currency} {exp.amount.toFixed(2)}</td>
              <td style={{ padding: '0.75rem' }}>
                <button onClick={() => deleteExpense(exp.id)} style={{ color: '#EF4444', background: 'transparent', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}