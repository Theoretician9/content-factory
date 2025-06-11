import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from './api';

interface User {
  email?: string;
  name?: string;
}

interface UserContextType {
  user: User | null;
  loading: boolean;
  error: string;
  logout: () => void;
  refreshProfile: () => void;
  clearError: () => void;
}

const UserContext = createContext<UserContextType>({
  user: null,
  loading: true,
  error: '',
  logout: () => {},
  refreshProfile: () => {},
  clearError: () => {},
});

export const useUser = () => useContext(UserContext);

export const UserProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  // Объявляем logout ПЕРЕД его использованием
  const logout = useCallback(async () => {
    try {
      console.log('🚪 Frontend: Начинаем logout...');
      
      // Отправляем запрос на сервер для инвалидации токенов
      const response = await apiFetch('/api/auth/logout', {
        method: 'POST'
      });
      
      if (response.ok) {
        console.log('✅ Logout successful on server');
      } else {
        console.warn('⚠️ Server logout failed, but clearing local storage anyway');
      }
    } catch (error) {
      console.warn('⚠️ Logout API call failed:', error);
    } finally {
      // Всегда очищаем локальное состояние, даже если сервер недоступен
      console.log('🧹 Frontend: Очищаем локальное состояние...');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
      setError('Вы вышли из аккаунта');
      navigate('/login');
    }
  }, [navigate]);

  const clearError = useCallback(() => {
    setError('');
  }, []);

  const fetchProfile = useCallback(() => {
    setLoading(true);
    setError('');
    apiFetch('/api/auth/me')
      .then(async (res) => {
        if (!res.ok) throw new Error('Ошибка получения профиля');
        const data = await res.json();
        setUser(data);
      })
      .catch((e) => {
        setUser(null);
        setError('Сессия истекла или ошибка авторизации');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  // Автоматическое обновление токена по таймеру (каждые 10 минут)
  useEffect(() => {
    const interval = setInterval(async () => {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const res = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
            credentials: 'include'
          });
          if (res.ok) {
            const data = await res.json();
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
          } else {
            logout();
          }
        } catch {
          logout();
        }
      }
    }, 10 * 60 * 1000); // 10 минут
    return () => clearInterval(interval);
  }, [logout]); // Добавляем logout в зависимости

  return (
    <UserContext.Provider value={{ user, loading, error, logout, refreshProfile: fetchProfile, clearError }}>
      {children}
    </UserContext.Provider>
  );
}; 