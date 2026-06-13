import axios from 'axios';

const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL,
  withCredentials: true,
});

// Add a response interceptor to handle 401 errors globally
api.interceptors.response.use(
  (response) => response, // Simply return the response if it's successful
  (error) => {
    // Check if the error is a 401 Unauthorized and not for an auth-related endpoint
    if (error.response && error.response.status === 401) {
      const originalRequestUrl = error.config.url;
      if (originalRequestUrl !== '/api/auth/login' && originalRequestUrl !== '/api/auth/me') {
        // Redirect to the login page only for client-side errors
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
      }
    }
    // For all other errors, just reject the promise
    return Promise.reject(error);
  }
);

export default api;