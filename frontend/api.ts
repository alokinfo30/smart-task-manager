import axios from 'axios';

let baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Dynamically align the API hostname with the browser's hostname to prevent 
// cross-origin cookie dropping (SameSite=lax) when using localhost vs 127.0.0.1.
if (typeof window !== 'undefined') {
  if (window.location.hostname === 'localhost' && baseURL.includes('127.0.0.1')) {
    baseURL = baseURL.replace('127.0.0.1', 'localhost');
  } else if (window.location.hostname === '127.0.0.1' && baseURL.includes('localhost')) {
    baseURL = baseURL.replace('localhost', '127.0.0.1');
  }
}

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