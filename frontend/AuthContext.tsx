"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { fetchWithAuth } from './app/fetchWithAuth';

// Define the user type based on what /api/auth/me returns
interface User {
  user_id: string;
  name: string;
  email: string;
  avatar: string;
}

interface AuthContextType {
  user: User | null;
  setUser: (user: User | null) => void;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Safely register Service Worker on the client to avoid SSR hydration mismatch
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      window.addEventListener('load', function() {
        navigator.serviceWorker.register('/sw.js').catch(() => {
          // Silently catch SW errors when testing across different ports/servers
        });
      });
    }

    const fetchUser = async () => {
      try {
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const response = await fetchWithAuth(`${API_BASE_URL}/api/auth/me`, {
          method: 'GET'
        });
  
        if (response.ok) {
          const data = await response.json();
          setUser(data);
        } else {
          setUser(null);
        }
      } catch (error) {
        setUser(null);
      } finally {
        setLoading(false);
      }
      };
    
      fetchUser();
  }, []);

  const login = async (username: string, password: string) => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    
    // Auto-remove spaces and symbols for real numbers, but allow demo accounts to bypass
    let finalUsername = username;
    if (username !== "demo_user" && !username.startsWith("demo_") && !username.startsWith("guest")) {
      finalUsername = username.replace(/\D/g, '');
      if (finalUsername.length !== 10) {
        throw new Error("Mobile number must be exactly 10 digits.");
      }
    }

    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mobile: finalUsername, pin: password }),
      credentials: 'include'
    });
    
    if (!response.ok) {
      const err = await response.json();
      let errMsg = 'Login failed';
      if (typeof err.detail === 'string') errMsg = err.detail;
      else if (Array.isArray(err.detail)) errMsg = err.detail[0]?.msg || errMsg;
      throw new Error(errMsg);
    }

    const data = await response.json();
    if (data.access_token) {
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
    }
    setUser(data);
    window.location.href = '/';
  };

   const logout = async () => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    try {
      await fetch(`${API_BASE_URL}/api/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (e) {
      console.error("Logout request failed", e);
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{ user, setUser, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};