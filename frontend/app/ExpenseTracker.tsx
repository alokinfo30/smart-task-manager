'use client';
 import React, { useState, useMemo } from 'react';
import { useAppStore } from './store';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { fetchWithAuth } from './fetchWithAuth';
import { useSWRConfig } from 'swr';

export default function ExpenseTracker({ expenses, fetchExpenses, recurringExpenses, recurringHistory, fetchRecurringExpenses, txt, speak, API_BASE_URL, currencySym, exportToCSV }: any) {
  const {
    currentUser,
    editExpenseId, setEditExpenseId,
    editExpenseData, setEditExpenseData,
    newExpAmount, setNewExpAmount,
    newExpCat, setNewExpCat,
    newExpDesc, setNewExpDesc,
    newExpDate, setNewExpDate,
  } = useAppStore();

  const [showManageRe, setShowManageRe] = useState(false);
  const [reAmount, setReAmount] = useState(0);
  const [reCategory, setReCategory] = useState("Food");
  const [reDesc, setReDesc] = useState("");
  const { mutate } = useSWRConfig();
  const expKey = currentUser ? `${API_BASE_URL}/api/expenses?user_id=${currentUser}` : null;

  const saveExpenseEdit = async () => {
    if (editExpenseId === null) return;
    if (expKey) mutate(expKey, { expenses: expenses.map((e: any) => e.id === editExpenseId ? { ...e, ...editExpenseData } : e) }, { revalidate: false });
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/edit`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expense_id: editExpenseId, user_id: currentUser, ...editExpenseData })
      });
      setEditExpenseId(null);
      speak("Expense updated");
    } catch (e) { console.error(e); }
    finally { fetchExpenses(); }
  };

  const deleteExpense = async (id: number) => {
    if (!window.confirm(txt.confirmDeleteExpense)) return;
    if (expKey) mutate(expKey, { expenses: expenses.filter((e: any) => e.id !== id) }, { revalidate: false });
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/${id}?user_id=${currentUser}`, { method: "DELETE" });
      speak("Expense deleted");
    } catch (e) { console.error(e); }
    finally { fetchExpenses(); }
  };

  const submitNewExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newExpAmount <= 0) { alert(txt.amountZeroError); return; }
    const tempId = Date.now();
    if (expKey) mutate(expKey, { expenses: [...expenses, { id: tempId, amount: newExpAmount, category: newExpCat, description: newExpDesc, date: newExpDate }] }, { revalidate: false });
    setNewExpAmount(0); setNewExpDesc("");
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: currentUser, amount: newExpAmount, category: newExpCat, description: newExpDesc, date: newExpDate })
      });
      speak("Expense added");
    } catch (e) { console.error(e); }
    finally { fetchExpenses(); }
  };

  const addRecurringExpense = async () => {
    if (reAmount <= 0 || !reDesc.trim()) return;
    try {
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/recurring`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: currentUser, amount: reAmount, category: reCategory, description: reDesc })
      });
      setReAmount(0); setReDesc(""); 
    } catch (e) { console.error(e); }
    finally { fetchRecurringExpenses(); }
  };

  const handleRecurringCheck = async (exp: any, action: 'added' | 'skipped') => {
    const todayStr = new Date().toISOString().split('T')[0];
    try {
      if (action === 'added') {
        await fetchWithAuth(`${API_BASE_URL}/api/expenses`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: currentUser, amount: exp.amount, category: exp.category, description: exp.description, date: todayStr })
        });
        speak("Recurring expense added to tracker");
      }
      await fetchWithAuth(`${API_BASE_URL}/api/expenses/recurring/check`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: currentUser, exp_id: exp.id, action, date: todayStr })
      });
    } catch (e) { console.error(e); }
    finally { fetchRecurringExpenses(); fetchExpenses(); }
  };

  const todayStr = new Date().toISOString().split('T')[0];
  const currentMonthStr = todayStr.substring(0, 7);
  
  const dailyTotal = useMemo(() => 
    expenses.filter((e: any) => e.date === todayStr).reduce((a: any, b: any) => a + (Number(b.amount) || 0), 0)
  , [expenses, todayStr]);

  const monthlyTotal = useMemo(() => 
    expenses.filter((e: any) => e.date?.startsWith(currentMonthStr)).reduce((a: any, b: any) => a + (Number(b.amount) || 0), 0)
  , [expenses, currentMonthStr]);

  const chartData = useMemo(() => {
    const data = [];
    for (let i = 29; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      const total = expenses
        .filter((e: any) => e.date === dateStr)
        .reduce((sum: number, exp: any) => sum + (Number(exp.amount) || 0), 0);
      data.push({ date: dateStr.substring(5), amount: total }); // MM-DD
    }
    return data;
  }, [expenses]);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div style={{ backgroundColor: '#F59E0B', color: 'white', padding: '15px', borderRadius: '8px 8px 0 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>{txt.expenseTracker}</h2>
        <button onClick={() => exportToCSV(expenses, 'expenses.csv')} style={{ padding: '5px 10px', backgroundColor: 'white', color: '#F59E0B', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold' }}>{txt.exportCsv}</button>
      </div>
      <div style={{ height: '30vh', overflowY: 'auto', backgroundColor: '#F9FAFB', padding: '20px', border: '1px solid #E5E7EB', borderTop: 'none' }}>
        <button onClick={() => setShowManageRe(!showManageRe)} style={{ width: '100%', padding: '10px', backgroundColor: '#F3F4F6', color: '#374151', border: '1px solid #E5E7EB', borderRadius: '4px', cursor: 'pointer', marginBottom: '15px', fontWeight: 'bold' }}>{showManageRe ? 'Hide' : txt.manageRecurring}</button>
        
        <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
          <div style={{ flex: 1, backgroundColor: 'white', padding: '10px', borderRadius: '8px', border: '1px solid #E5E7EB', textAlign: 'center' }}>
            <div style={{ fontSize: '12px', color: '#6B7280' }}>{txt.dailyTotal}</div>
            <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#EF4444' }}>{currencySym}{(dailyTotal || 0).toFixed(2)}</div>
          </div>
          <div style={{ flex: 1, backgroundColor: 'white', padding: '10px', borderRadius: '8px', border: '1px solid #E5E7EB', textAlign: 'center' }}>
            <div style={{ fontSize: '12px', color: '#6B7280' }}>{txt.monthlyTotal}</div>
            <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#EF4444' }}>{currencySym}{(monthlyTotal || 0).toFixed(2)}</div>
          </div>
        </div>
        
        <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: 'white', border: '1px solid #E5E7EB', borderRadius: '8px', height: '250px' }}>
          <h4 style={{ margin: '0 0 10px 0', color: '#4B5563' }}>30-Day Trend</h4>
          <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} tickFormatter={(val) => `${currencySym}${val}`} width={50} />
              <Tooltip formatter={(value: number) => [`${currencySym}${value.toFixed(2)}`, 'Spent']} labelStyle={{ color: 'black' }} />
              <Line type="monotone" dataKey="amount" stroke="#EF4444" strokeWidth={3} dot={{ r: 3, fill: '#EF4444' }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {showManageRe && (
          <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: 'white', border: '1px solid #E5E7EB', borderRadius: '8px' }}>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
              <input type="number" value={reAmount} onChange={e => setReAmount(parseFloat(e.target.value) || 0)} style={{ flex: 1, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }} placeholder="Amount" />
              <select value={reCategory} onChange={e => setReCategory(e.target.value)} style={{ flex: 1, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}>
                <option>Food</option><option>Transport</option><option>Shopping</option><option>Bills</option><option>Other</option>
              </select>
              <input type="text" value={reDesc} onChange={e => setReDesc(e.target.value)} style={{ flex: 2, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }} placeholder="Description" />
              <button onClick={addRecurringExpense} style={{ padding: '8px 15px', backgroundColor: '#F59E0B', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>{txt.addRecurring}</button>
            </div>
            {recurringExpenses.map((r: any) => (
              <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #E5E7EB' }}>
                <span>{r.description} - {currencySym}{r.amount} ({r.category})</span>
                <button onClick={async () => { if(window.confirm('Delete?')){ await fetchWithAuth(`${API_BASE_URL}/api/expenses/recurring/${r.id}?user_id=${currentUser}`, {method: 'DELETE'}); fetchRecurringExpenses();} }} style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer' }}>🗑️</button>
              </div>
            ))}
          </div>
        )}

        {recurringExpenses.filter((r: any) => !(recurringHistory[new Date().toISOString().split('T')[0]]?.[r.id])).length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ margin: '0 0 10px 0', color: '#4B5563' }}>{txt.recurringTitle}</h4>
            {recurringExpenses.filter((r: any) => !(recurringHistory[new Date().toISOString().split('T')[0]]?.[r.id])).map((r: any) => (
              <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '15px', backgroundColor: '#FEF3C7', border: '1px solid #FDE68A', borderRadius: '8px', marginBottom: '10px' }}>
                <span><strong>{r.description}</strong> - {currencySym}{r.amount} ({r.category})</span>
                <div style={{ display: 'flex', gap: '5px' }}>
                  <button onClick={() => handleRecurringCheck(r, 'added')} style={{ padding: '5px 10px', backgroundColor: '#10B981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>{txt.add}</button>
                  <button onClick={() => handleRecurringCheck(r, 'skipped')} style={{ padding: '5px 10px', backgroundColor: '#9CA3AF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>{txt.skip}</button>
                </div>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={submitNewExpense} style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
          <input type="number" value={newExpAmount} onChange={e => setNewExpAmount(parseFloat(e.target.value) || 0)} style={{ flex: 1, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }} placeholder="Amount" />
          <select value={newExpCat} onChange={e => setNewExpCat(e.target.value)} style={{ flex: 1, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}>
            <option>Food</option><option>Transport</option><option>Shopping</option><option>Bills</option><option>Other</option>
          </select>
          <input type="text" value={newExpDesc} onChange={e => setNewExpDesc(e.target.value)} style={{ flex: 2, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }} placeholder="Description" required />
          <input type="date" value={newExpDate} onChange={e => setNewExpDate(e.target.value)} style={{ flex: 1, padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }} required />
          <button type="submit" style={{ padding: '8px 15px', backgroundColor: '#F59E0B', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>{txt.addExpense}</button>
        </form>

        {expenses.length === 0 ? (
          <p style={{ color: '#6B7280' }}>{txt.noExpenses}</p>
        ) : (
          expenses.map((exp: any) => (
            <div key={exp.id} style={{ backgroundColor: 'white', padding: '15px', borderRadius: '8px', border: '1px solid #E5E7EB', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
              {editExpenseId === exp.id ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '100%' }}>
                  <input type="text" value={editExpenseData.description} onChange={e => setEditExpenseData({...editExpenseData, description: e.target.value})} style={{ padding: '5px', border: '1px solid #ccc', borderRadius: '4px' }} placeholder="Description" />
                  <input type="number" value={editExpenseData.amount} onChange={e => setEditExpenseData({...editExpenseData, amount: parseFloat(e.target.value) || 0})} style={{ padding: '5px', border: '1px solid #ccc', borderRadius: '4px' }} placeholder="Amount" />
                  <input type="text" value={editExpenseData.category} onChange={e => setEditExpenseData({...editExpenseData, category: e.target.value})} style={{ padding: '5px', border: '1px solid #ccc', borderRadius: '4px' }} placeholder="Category" />
                  <input type="date" value={editExpenseData.date} onChange={e => setEditExpenseData({...editExpenseData, date: e.target.value})} style={{ padding: '5px', border: '1px solid #ccc', borderRadius: '4px' }} />
                  <div style={{ display: 'flex', gap: '5px' }}>
                    <button onClick={saveExpenseEdit} style={{ padding: '5px 10px', backgroundColor: '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
                    <button onClick={() => setEditExpenseId(null)} style={{ padding: '5px 10px', backgroundColor: '#9CA3AF', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
                  </div>
                </div>
              ) : (
                <>
                  <div>
                    <h3 style={{ margin: '0 0 5px 0' }}>{exp.description}</h3>
                    <div style={{ fontSize: '14px', color: '#4B5563' }}>{exp.category} | {exp.date}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <span style={{ fontSize: '18px', fontWeight: 'bold', color: '#EF4444' }}>{currencySym}{Number(exp.amount).toFixed(2)}</span>
                    <button onClick={() => { setEditExpenseId(exp.id); setEditExpenseData({ amount: exp.amount, category: exp.category, description: exp.description, date: exp.date }); }} style={{ padding: '5px 10px', backgroundColor: '#F59E0B', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>✏️</button>
                    <button onClick={() => deleteExpense(exp.id)} style={{ padding: '5px 10px', backgroundColor: '#EF4444', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>🗑️</button>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}