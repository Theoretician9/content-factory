import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { api, apiFetch } from '../api';

interface CardConfig {
  key: string;
  title: string;
  fetch: () => Promise<Response>;
  fields: { label: string; key: string }[];
}

const cards: CardConfig[] = [
  {
    key: 'tariff',
    title: 'Текущий тариф',
    fetch: api.getTariff,
    fields: [
      { label: 'Название тарифа', key: 'name' },
    ],
  },
  {
    key: 'mailing',
    title: 'Рассылки/Инвайт',
    fetch: api.getMailingStatus,
    fields: [
      { label: 'Статус', key: 'status' },
      { label: 'Добавлено', key: 'added' },
      { label: 'Сообщений отправлено', key: 'sent' },
    ],
  },
  {
    key: 'integrations',
    title: 'Интеграции',
    fetch: api.getIntegrationsStatus,
    fields: [
      { label: 'Статус', key: 'status' },
      { label: 'Активных интеграций', key: 'active' },
    ],
  },
  {
    key: 'autocall',
    title: 'Автообзвон',
    fetch: api.getAutocallStatus,
    fields: [
      { label: 'Статус', key: 'status' },
      { label: 'Звонков сегодня', key: 'calls_today' },
    ],
  },
  {
    key: 'funnels',
    title: 'Воронки',
    fetch: api.getFunnelsStatus,
    fields: [
      { label: 'Статус', key: 'status' },
      { label: 'Активных воронок', key: 'active' },
    ],
  },
  {
    key: 'parsing',
    title: 'Парсинг',
    fetch: api.getParsingStatus,
    fields: [
      { label: 'Статус', key: 'status' },
      { label: 'Задач в очереди', key: 'queue' },
    ],
  },
  {
    key: 'analytics',
    title: 'Аналитика',
    fetch: api.getAnalytics,
    fields: [
      { label: 'Статус', key: 'status' },
      { label: 'Показателей', key: 'metrics' },
    ],
  },
];

const Dashboard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<{ email?: string; name?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [cardData, setCardData] = useState<Record<string, any>>({});
  const [cardLoading, setCardLoading] = useState<Record<string, boolean>>({});
  const [cardError, setCardError] = useState<Record<string, string>>({});

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
    cards.forEach((card) => {
      setCardLoading((prev) => ({ ...prev, [card.key]: true }));
      setCardError((prev) => ({ ...prev, [card.key]: '' }));
      card.fetch()
        .then(async (res) => {
          if (!res.ok) throw new Error('Ошибка');
          const data = await res.json();
          setCardData((prev) => ({ ...prev, [card.key]: data }));
        })
        .catch(() => setCardError((prev) => ({ ...prev, [card.key]: 'Нет данных/Ошибка подключения' })))
        .finally(() => setCardLoading((prev) => ({ ...prev, [card.key]: false })));
    });
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto w-full">
            {cards.map((card) => (
              <div key={card.key} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 flex flex-col gap-3">
                <div className="font-semibold text-lg mb-2">{card.title}</div>
                {cardLoading[card.key] ? (
                  <div className="text-gray-400">Загрузка...</div>
                ) : cardError[card.key] ? (
                  <div className="text-red-500">{cardError[card.key]}</div>
                ) : (
                  <>
                    {card.fields.map((field) => (
                      <div key={field.key}>
                        {field.label}: <span className="font-semibold">{cardData[card.key]?.[field.key] ?? '—'}</span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            ))}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Dashboard; 