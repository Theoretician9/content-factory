import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { apiFetch } from '../api';

const Dashboard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<{ email?: string; name?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [tariff, setTariff] = useState<string>('');
  const [tariffLoading, setTariffLoading] = useState(true);
  const [tariffError, setTariffError] = useState('');

  const [mailing, setMailing] = useState<{ status?: string; added?: number; sent?: number } | null>(null);
  const [mailingLoading, setMailingLoading] = useState(true);
  const [mailingError, setMailingError] = useState('');

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

  useEffect(() => {
    setTariffLoading(true);
    setTariffError('');
    apiFetch('/api/billing/tariff')
      .then(async (res) => {
        if (!res.ok) throw new Error('Ошибка получения тарифа');
        const data = await res.json();
        setTariff(data?.name || '—');
      })
      .catch(() => setTariffError('Нет данных/Ошибка подключения'))
      .finally(() => setTariffLoading(false));
  }, []);

  useEffect(() => {
    setMailingLoading(true);
    setMailingError('');
    apiFetch('/api/mailing/status')
      .then(async (res) => {
        if (!res.ok) throw new Error('Ошибка получения статуса рассылки');
        const data = await res.json();
        setMailing({
          status: data?.status || '—',
          added: data?.added ?? 0,
          sent: data?.sent ?? 0,
        });
      })
      .catch(() => setMailingError('Нет данных/Ошибка подключения'))
      .finally(() => setMailingLoading(false));
  }, []);

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
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar />
      <div className="flex-1 flex flex-col min-h-screen">
        <Header title="Главная" />
        <main className="flex-1 p-8 flex flex-col gap-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto w-full">
            {/* Текущий тариф */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 flex flex-col gap-3">
              <div className="font-semibold text-lg mb-2">Текущий тариф</div>
              {tariffLoading ? (
                <div className="text-gray-400">Загрузка...</div>
              ) : tariffError ? (
                <div className="text-red-500">{tariffError}</div>
              ) : (
                <div className="flex gap-2 items-center">
                  <input
                    type="text"
                    value={tariff}
                    readOnly
                    className="border border-gray-300 dark:border-gray-700 rounded px-3 py-2 bg-gray-100 dark:bg-gray-900 text-gray-700 dark:text-gray-200 w-64"
                  />
                  <button className="ml-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition">Изменить</button>
                </div>
              )}
            </div>
            {/* Рассылки/Инвайт */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 flex flex-col gap-3">
              <div className="font-semibold text-lg mb-2">Рассылки/Инвайт</div>
              {mailingLoading ? (
                <div className="text-gray-400">Загрузка...</div>
              ) : mailingError ? (
                <div className="text-red-500">{mailingError}</div>
              ) : (
                <>
                  <div>Статус: <span className="font-semibold">{mailing?.status}</span></div>
                  <div>Добавлено: <span className="font-semibold">{mailing?.added}</span></div>
                  <div>Сообщений отправлено: <span className="font-semibold">{mailing?.sent}</span></div>
                </>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default Dashboard; 