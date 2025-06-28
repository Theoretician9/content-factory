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
    
    // ✅ Проверка авторизации по QR коду
    checkQRAuthorization: (password?: string) => apiFetch('/api/integrations/telegram/qr-check', {
      method: 'POST',
      body: JSON.stringify(password ? { password } : {})
    }),
    
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
      // Увеличенный таймаут для поиска сообществ (120 секунд для FloodWait)
      return apiFetch(`/api/parsing/search?${searchParams}`, {
        timeout: 120000 // 120 секунд (2 минуты)
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

// API функции для Invite Service
export const inviteApi = {
  // Health checks
  health: () => apiFetch('/api/invite/health'),
  healthDetailed: () => apiFetch('/api/invite/health/detailed'),

  // Задачи приглашений
  tasks: {
    // Создание задачи приглашений
    create: (data: {
      platform: 'telegram' | 'instagram' | 'whatsapp';
      task_type: 'invite_to_group' | 'send_messages';
      title: string;
      description?: string;
      target_group_id?: string; // для приглашений в группу
      message_template?: string; // для личных сообщений
      priority?: 'HIGH' | 'NORMAL' | 'LOW';
      settings?: {
        delay_between_invites?: number;
        batch_size?: number;
        auto_add_contacts?: boolean;
        fallback_to_messages?: boolean;
      };
    }) => apiFetch('/api/invite/tasks', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

    // Получение списка задач
    list: (params: {
      platform?: 'telegram' | 'instagram' | 'whatsapp';
      status?: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
      page?: number;
      limit?: number;
    } = {}) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
      return apiFetch(`/api/invite/tasks?${searchParams}`);
    },

    // Получение конкретной задачи
    get: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}`),

    // Обновление задачи
    update: (taskId: string, data: Partial<{
      title: string;
      description: string;
      message_template: string;
      settings: any;
    }>) => apiFetch(`/api/invite/tasks/${taskId}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

    // Удаление задачи
    delete: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}`, {
      method: 'DELETE'
    })
  },

  // Управление выполнением
  execution: {
    // Запуск задачи
    start: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}/execute`, {
      method: 'POST'
    }),

    // Пауза задачи
    pause: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}/pause`, {
      method: 'POST'
    }),

    // Возобновление задачи
    resume: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}/resume`, {
      method: 'POST'
    }),

    // Отмена задачи
    cancel: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}/cancel`, {
      method: 'POST'
    }),

    // Получение статуса задачи
    status: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}/status`),

    // Получение детальной статистики
    stats: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}/stats`),

    // Получение логов выполнения
    logs: (taskId: string, params: {
      limit?: number;
      offset?: number;
      action?: string;
      status?: string;
    } = {}) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, value.toString());
        }
      });
      return apiFetch(`/api/invite/tasks/${taskId}/logs?${searchParams}`);
    },

    // Получение доступных аккаунтов для задачи
    accounts: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}/accounts`),

    // Тестовое приглашение
    testInvite: (taskId: string, data: {
      target_id: string;
      account_id?: string;
    }) => apiFetch(`/api/invite/tasks/${taskId}/test-invite`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  // Импорт аудитории
  import: {
    // Импорт из файла
    file: (taskId: string, file: File, options: {
      source_name?: string;
      field_mapping?: Record<string, string>;
    } = {}) => {
      const formData = new FormData();
      formData.append('file', file);
      if (options.source_name) {
        formData.append('source_name', options.source_name);
      }
      if (options.field_mapping) {
        formData.append('field_mapping', JSON.stringify(options.field_mapping));
      }

      const token = localStorage.getItem('access_token');
      return fetch(`/api/invite/tasks/${taskId}/import/file`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });
    },

    // Импорт из parsing-service
    parsing: (taskId: string, data: {
      parsing_task_id: string;
      source_name?: string;
      filter_criteria?: any;
    }) => apiFetch(`/api/invite/tasks/${taskId}/import/parsing`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

    // Валидация импортированных данных
    validate: (taskId: string) => apiFetch(`/api/invite/tasks/${taskId}/import/validate`)
  },

  // Статистика и отчеты
  stats: {
    // Общая статистика по всем задачам
    overview: () => apiFetch('/api/invite/stats'),

    // Статистика по платформе
    platform: (platform: 'telegram' | 'instagram' | 'whatsapp') => 
      apiFetch(`/api/invite/stats/${platform}`),

    // Экспорт отчета
    export: (taskId: string, format: 'json' | 'csv' | 'excel') => 
      apiFetch(`/api/invite/tasks/${taskId}/report?format=${format}`)
  },

  // Служебные функции
  accounts: () => apiFetch('/api/invite/accounts'), // Доступные аккаунты пользователя
  
  // Получение списка задач parsing-service для импорта
  parsingTasks: () => apiFetch('/api/invite/parsing-tasks')
};