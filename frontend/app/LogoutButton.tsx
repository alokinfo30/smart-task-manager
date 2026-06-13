'use client';

import React from 'react';
import { useAuth } from '../AuthContext';

export default function LogoutButton() {
  const { logout } = useAuth();

  return (
    <button 
      onClick={logout} 
      style={{ padding: '0.5rem 1rem', backgroundColor: '#EF4444', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}>
      Logout
    </button>
  );
}