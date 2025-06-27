// Расширенный тип для RequestInit с timeout
interface ExtendedRequestInit extends RequestInit {
  timeout?: number;
}

export async function apiFetch(url: string, options: ExtendedRequestInit = {}) {
  let accessToken = localStorage.getItem('access_token');
  let refreshToken = localStorage.getItem('refresh_token');
  const headers = {
    ...(options.headers || {}),
    'Content-Type': 'application/json',
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };
  
  // Создаем AbortController для управления таймаутом
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || 30000); // Default 30s, можно переопределить
  
  try {
    let res = await fetch(url, { 
      ...options, 
      headers,
      credentials: 'include', // Важно для передачи cookies (refresh_token)
      signal: controller.signal
    });
    
    clearTimeout(timeoutId); // Очищаем таймаут если запрос успешен
    
    if (res.status === 401 && refreshToken) {
      // Попробовать refresh
      const refreshRes = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
        credentials: 'include'
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
        res = await fetch(url, { 
          ...options, 
          headers: retryHeaders,
          credentials: 'include'
        });
      } else {
        // refresh не удался — logout
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login?expired=1';
        throw new Error('Session expired');
      }
    }
    return res;
  } catch (error: any) {
    clearTimeout(timeoutId); // Очищаем таймаут при ошибке
    
    // Обработка ошибки таймаута
    if (error.name === 'AbortError') {
      throw new Error(`Request timeout after ${options.timeout || 30000}ms`);
    }
    
    // Прочие ошибки
    throw error;
  }
}

// Централизованные функции для микросервисов
export const api = {
  getTariff: () => apiFetch('/api/billing/tariff'),
  getMailingStatus: () => apiFetch('/api/mailing/status'),
  getIntegrationsStatus: async () => {
    try {
      // Получаем статистику интеграций
      const [accountsRes, statsRes] = await Promise.all([
        integrationApi.telegram.getAccounts(),
        integrationApi.telegram.getErrorStats(7)
      ]);

      let activeAccounts = 0;
      let status = 'error';

      if (accountsRes.ok) {
        const accounts = await accountsRes.json();
        activeAccounts = accounts.filter((acc: any) => acc.is_active).length;
        status = activeAccounts > 0 ? 'active' : 'inactive';
      }

      // Возвращаем данные в том же формате что ожидает Dashboard
      return new Response(JSON.stringify({
        status: status,
        active: activeAccounts
      }), { 
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      return new Response(JSON.stringify({
        status: 'error',
        active: 0
      }), { 
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  },
  getAutocallStatus: () => apiFetch('/api/autocall/status'),
  getFunnelsStatus: () => apiFetch('/api/funnels/status'),
  getParsingStatus: () => apiFetch('/api/parsing/status'),
  getAnalytics: () => apiFetch('/api/analytics/summary'),
  // ...добавлять новые сервисы по мере необходимости
};

// API функции для Integration Service
export const integrationApi = {
  // Health checks
  health: () => apiFetch('/api/integrations/health'),
  healthDetailed: () => apiFetch('/api/integrations/health/detailed'),

  // Telegram API
  telegram: {
    // Получение аккаунтов
    getAccounts: (activeOnly = true) => apiFetch(`/api/integrations/telegram/accounts?active_only=${activeOnly}`),
    
    // Получение конкретного аккаунта
    getAccount: (sessionId: string) => apiFetch(`/api/integrations/telegram/accounts/${sessionId}`),
    
    // Подключение аккаунта
    connectAccount: (data: { phone: string; code?: string; password?: string }) => 
      apiFetch('/api/integrations/telegram/connect', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    
    // Генерация QR кода
    generateQR: () => apiFetch('/api/integrations/telegram/qr-code'),
    
    // Отключение аккаунта
    disconnectAccount: (sessionId: string) => 
      apiFetch(`/api/integrations/telegram/accounts/${sessionId}`, {
        method: 'DELETE'
      }),
    
    // Переподключение аккаунта
    reconnectAccount: (sessionId: string) => 
      apiFetch(`/api/integrations/telegram/accounts/${sessionId}/reconnect`, {
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
      return apiFetch(`/api/integrations/telegram/logs?${searchParams}`);
    },
    
    // Статистика ошибок
    getErrorStats: (daysBack = 7) => 
      apiFetch(`/api/integrations/telegram/stats/errors?days_back=${daysBack}`)
  }
}; 

// API функции для Parsing Service (мультиплатформенный)
export const parsingApi = {
  // Health checks
  health: () => apiFetch('/api/parsing/health'),
  
  // Задачи парсинга
  tasks: {
    // Создание задачи парсинга
    create: (data: {
      platform: 'telegram' | 'instagram' | 'whatsapp';
      links: string[];
      priority?: 'low' | 'normal' | 'high';
      parsing_speed?: 'safe' | 'medium' | 'fast';
      settings?: {
        max_depth?: number;
        include_media?: boolean;
        date_from?: string;
        date_to?: string;
      };
    }) => apiFetch('/api/parsing/tasks', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    
    // Получение списка задач
    list: (params: {
      platform?: 'telegram' | 'instagram' | 'whatsapp';
      status?: 'pending' | 'running' | 'completed' | 'failed' | 'paused';
      page?: number;
      limit?: number;
    } = {}) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
      return apiFetch(`/api/parsing/tasks?${searchParams}`);
    },
    
    // Получение конкретной задачи
    get: (taskId: string) => apiFetch(`/api/parsing/tasks/${taskId}`),
    
    // Пауза задачи
    pause: (taskId: string) => apiFetch(`/api/parsing/tasks/${taskId}/pause`, {
      method: 'POST'
    }),
    
    // Возобновление задачи  
    resume: (taskId: string) => apiFetch(`/api/parsing/tasks/${taskId}/resume`, {
      method: 'POST'
    }),
    
    // Удаление задачи
    delete: (taskId: string) => apiFetch(`/api/parsing/tasks/${taskId}`, {
      method: 'DELETE'
    })
  },
  
  // Результаты парсинга
  results: {
    // Получение результатов задачи
    get: (taskId: string, params: {
      format?: 'json' | 'csv' | 'excel';
      platform_filter?: string;
      limit?: number;
      offset?: number;
    } = {}) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
      return apiFetch(`/api/parsing/results/${taskId}?${searchParams}`);
    },
    
    // Экспорт результатов
    export: (taskId: string, format: 'json' | 'csv' | 'excel') => 
      apiFetch(`/api/parsing/results/${taskId}/export?format=${format}`)
  },
  
  // Поиск сообществ
  search: {
    // Поиск сообществ по ключевым словам с увеличенным таймаутом
    communities: (params: {
      platform: 'telegram' | 'instagram' | 'whatsapp';
      query: string;
      offset?: number;
      limit?: number;
      speed?: 'fast' | 'medium' | 'safe';
    }) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
      // Увеличенный таймаут для поиска сообществ (60 секунд)
      return apiFetch(`/api/parsing/search?${searchParams}`, {
        timeout: 60000 // 60 секунд
      });
    }
  },
  
  // Статистика
  stats: {
    // Общая статистика по платформам
    overview: () => apiFetch('/api/parsing/stats'),
    
    // Статистика по конкретной платформе
    platform: (platform: 'telegram' | 'instagram' | 'whatsapp') => 
      apiFetch(`/api/parsing/stats/${platform}`)
  }
};