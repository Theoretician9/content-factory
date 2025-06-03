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

// Централизованные функции для микросервисов
export const api = {
  getTariff: () => apiFetch('/api/billing/tariff'),
  getMailingStatus: () => apiFetch('/api/mailing/status'),
  getIntegrationsStatus: () => apiFetch('/api/integrations/status'),
  getAutocallStatus: () => apiFetch('/api/autocall/status'),
  getFunnelsStatus: () => apiFetch('/api/funnels/status'),
  getParsingStatus: () => apiFetch('/api/parsing/status'),
  getAnalytics: () => apiFetch('/api/analytics/summary'),
  // ...добавлять новые сервисы по мере необходимости
};

// API функции для Integration Service
export const integrationApi = {
  // Health checks
  health: () => apiFetch('http://localhost:8001/health'),
  healthDetailed: () => apiFetch('http://localhost:8001/api/v1/health/detailed'),

  // Telegram API
  telegram: {
    // Получение аккаунтов
    getAccounts: (activeOnly = true) => apiFetch(`http://localhost:8001/api/v1/telegram/accounts?active_only=${activeOnly}`),
    
    // Получение конкретного аккаунта
    getAccount: (sessionId: string) => apiFetch(`http://localhost:8001/api/v1/telegram/accounts/${sessionId}`),
    
    // Подключение аккаунта
    connectAccount: (data: { phone: string; code?: string; password?: string }) => 
      apiFetch('http://localhost:8001/api/v1/telegram/connect', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    
    // Генерация QR кода
    generateQR: () => apiFetch('http://localhost:8001/api/v1/telegram/qr-code'),
    
    // Отключение аккаунта
    disconnectAccount: (sessionId: string) => 
      apiFetch(`http://localhost:8001/api/v1/telegram/accounts/${sessionId}`, {
        method: 'DELETE'
      }),
    
    // Переподключение аккаунта
    reconnectAccount: (sessionId: string) => 
      apiFetch(`http://localhost:8001/api/v1/telegram/accounts/${sessionId}/reconnect`, {
        method: 'POST'
      }),
    
    // Логи интеграций
    getLogs: (params: {
      integration_type?: string;
      log_status?: string;
      days_back?: number;
      page?: number;
      size?: number;
    } = {}) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
      return apiFetch(`http://localhost:8001/api/v1/telegram/logs?${searchParams}`);
    },
    
    // Статистика ошибок
    getErrorStats: (daysBack = 7) => 
      apiFetch(`http://localhost:8001/api/v1/telegram/stats/errors?days_back=${daysBack}`)
  }
}; 