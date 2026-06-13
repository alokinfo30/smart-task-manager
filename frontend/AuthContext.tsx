"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import api from './api'; // The configured axios instance

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
        navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW registration failed:', err));
      });
    }

    const checkUserAuthentication = async () => {
      try {
        // The stm_token cookie is sent automatically due to `withCredentials: true`
        const response = await api.get('/api/auth/me');
        setUser(response.data);
      } catch (error) {
        // If the /me endpoint fails (e.g., 401), the user is not logged in.
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    checkUserAuthentication();
  }, []);

  const login = async (username: string, password: string) => {
    // The backend expects a JSON payload with "mobile" and "pin"
    const response = await api.post('/api/auth/login', {
      mobile: username,
      pin: password
    });
    
    setUser(response.data);
    window.location.href = '/';
  };

   const logout = async () => {
    await api.post('/api/auth/logout');
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