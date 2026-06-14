let reconnectQueuePromise = Promise.resolve();
let queueCount = 0;
let isLoggingOut = false;

export const fetchWithAuth = async (
  url: string,
  options: RequestInit = {},
  retries = 3,
  backoff = 300
): Promise<Response> => {
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  
  const getTokens = () => ({
    accessToken: localStorage.getItem('access_token') || sessionStorage.getItem('access_token'),
    refreshToken: localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token'),
    storage: localStorage.getItem('refresh_token') ? localStorage : sessionStorage
  });

  const handleLogout = () => {
    if (isLoggingOut) return;
    isLoggingOut = true;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('refresh_token');
    localStorage.removeItem('stm_user');
    sessionStorage.removeItem('stm_user');
    window.location.reload();
  };

  const attemptRefresh = async (refreshToken: string, storage: Storage) => {
    try {
      const refreshResponse = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
        credentials: 'include'
      });
      
      if (refreshResponse.ok) {
        const data = await refreshResponse.json();
        storage.setItem('access_token', data.access_token);
        if (data.refresh_token) {
          storage.setItem('refresh_token', data.refresh_token);
        }
        return data.access_token;
      } else {
        handleLogout();
        return null;
      }
    } catch (err) {
      console.error("Token refresh failed", err);
      handleLogout();
      return null;
    }
  };

  const isTokenExpired = (token: string) => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const exp = payload.exp * 1000;
      return Date.now() > exp - 60000; // Refresh proactively if expiring within 1 minute
    } catch (e) {
      return false;
    }
  };

  const executeRequest = async (): Promise<Response> => {
    let { accessToken, refreshToken, storage } = getTokens();

    // 1. Proactively refresh token before making the request if needed
    if (accessToken && isTokenExpired(accessToken) && refreshToken) {
      accessToken = await attemptRefresh(refreshToken, storage);
    }

    const headers = new Headers(options.headers || {});
    if (accessToken) {
      headers.set('Authorization', `Bearer ${accessToken}`);
    }

    try {
      let response = await fetch(url, { credentials: 'include', ...options, headers });

      // 2. Reactively refresh token if we get an unexpected 401
      if (response.status === 401 && !url.includes('/api/auth/')) {
        if (refreshToken) {
          accessToken = await attemptRefresh(refreshToken, storage);
          if (accessToken) {
            headers.set('Authorization', `Bearer ${accessToken}`);
            response = await fetch(url, { credentials: 'include', ...options, headers });
          }
        }
        
        if (response.status === 401) {
          handleLogout();
        }
      }

      // 3. Retry on temporary server errors or rate limiting
      if ((response.status >= 500 || response.status === 429) && retries > 0) {
        await new Promise(resolve => setTimeout(resolve, backoff));
        return fetchWithAuth(url, options, retries - 1, backoff * 2);
      }

      return response;
    } catch (error) {
      // If the failure occurred due to a connection dropping mid-request
      if (typeof window !== 'undefined' && !navigator.onLine) {
        console.warn("Connection dropped during request. Waiting to retry...");
        await new Promise<void>(resolve => window.addEventListener('online', () => resolve(), { once: true }));
        return fetchWithAuth(url, options, retries, backoff); // Retry without consuming a retry attempt
      }

      // Retry on network failures
      if (retries > 0) {
        await new Promise(resolve => setTimeout(resolve, backoff));
        return fetchWithAuth(url, options, retries - 1, backoff * 2);
      }
      throw error;
    }
  };

  // 0. Pause execution and sequentially queue requests if offline to prevent 429 Rate Limits upon reconnection
  if (typeof window !== 'undefined' && !navigator.onLine) {
    console.warn("App is offline. Queuing request until connection is restored...");
    queueCount++;
    window.dispatchEvent(new CustomEvent('stm_sync_status', { detail: { syncing: true, count: queueCount } }));
    await new Promise<void>(resolve => window.addEventListener('online', () => resolve(), { once: true }));
    console.log("Connection restored. Resuming request sequentially...");
    
    return new Promise<Response>((resolve, reject) => {
      reconnectQueuePromise = reconnectQueuePromise.then(async () => {
        try {
          // 250ms spacing between queued requests prevents server overload
          await new Promise(res => setTimeout(res, 250));
          const response = await executeRequest();
          resolve(response);
        } catch (err) {
          reject(err);
        } finally {
          queueCount--;
          window.dispatchEvent(new CustomEvent('stm_sync_status', { detail: { syncing: queueCount > 0, count: queueCount } }));
        }
      });
    });
  }

  return executeRequest();
};