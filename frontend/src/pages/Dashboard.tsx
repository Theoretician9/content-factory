import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiFetch } from '../api';

const Dashboard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<{ email?: string; name?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError('');
    apiFetch('/api/auth/me')
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 502) {
            setError('Сервис пользователей временно недоступен. Попробуйте позже.');
          } else if (res.status === 500) {
            setError('Внутренняя ошибка сервера.');
          } else {
            const data = await res.json();
            setError(data.detail || 'Ошибка авторизации');
          }
          setUser(null);
        } else {
          const data = await res.json();
          setUser(data);
        }
      })
      .catch(() => {
        setError('Ошибка сети или сервера');
        setUser(null);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    if (location.search.includes('expired=1')) {
      setError('Сессия истекла, войдите снова');
    }
    return () => { ignore = true; };
  }, [location.search]);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  if (loading) {
    return <div className="flex flex-col items-center justify-center min-h-screen text-lg">Загрузка...</div>;
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen text-lg text-red-600">
        <div className="mb-4">{error}</div>
        <button
          onClick={handleLogout}
          className="mt-4 bg-blue-500 text-white px-6 py-2 rounded-lg font-semibold hover:bg-blue-600 transition-all duration-200"
        >
          Выйти
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-2xl font-bold mb-4">{t('dashboard')}</h1>
      {user && (
        <div className="mb-4 text-lg">Добро пожаловать, {user.name || user.email}!</div>
      )}
      <p>Dashboard content will be here</p>
      <button
        onClick={handleLogout}
        className="mt-8 bg-red-500 text-white px-6 py-2 rounded-lg font-semibold hover:bg-red-600 transition-all duration-200"
      >
        Выйти
      </button>
    </div>
  );
};

export default Dashboard; 