export async function apiFetch(url: string, options: RequestInit = {}) {
  let accessToken = localStorage.getItem('access_token');
  let refreshToken = localStorage.getItem('refresh_token');
  const headers = {
    ...(options.headers || {}),
    'Content-Type': 'application/json',
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };
  let res = await fetch(url, { ...options, headers });
  if (res.status === 401 && refreshToken) {
    // Попробовать refresh
    const refreshRes = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      // Повторить исходный запрос с новым access_token
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${data.access_token}`
      };
      res = await fetch(url, { ...options, headers: retryHeaders });
    } else {
      // refresh не удался — logout
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login?expired=1';
      throw new Error('Session expired');
    }
  }
  return res;
} 