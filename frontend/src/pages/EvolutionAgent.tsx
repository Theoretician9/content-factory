import React, { useEffect, useMemo, useState } from 'react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { evolutionApi } from '../api';

interface CalendarSlot {
  slot_id: string;
  dt: string;
  pillar?: string | null;
  status: string;
  channel_id: string;
}

interface OnboardResponse {
  strategy_id: string;
  channel_id: string;
  slots: CalendarSlot[];
}

type EvolutionTab = 'launch' | 'channels' | 'details';

interface ChannelSummaryStats {
  total_slots: number;
  planned: number;
  processing: number;
  ready: number;
  published: number;
  failed: number;
  total_posts: number;
  total_memory_logs: number;
  last_published_at?: string | null;
}

interface ChannelSummary {
  channel_id: string;
  description?: string;
  persona?: any;
  content_mix?: any;
  schedule_rules?: any;
  stats: ChannelSummaryStats;
}

const EvolutionAgent: React.FC = () => {
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 768);

  const [channelId, setChannelId] = useState('');
  const [description, setDescription] = useState('');
  const [tone, setTone] = useState('дружелюбный эксперт');
  const [language, setLanguage] = useState<'ru' | 'en'>('ru');

  const [onboardLoading, setOnboardLoading] = useState(false);
  const [onboardError, setOnboardError] = useState('');
  const [onboardResult, setOnboardResult] = useState<OnboardResponse | null>(null);

  const [calendarChannelId, setCalendarChannelId] = useState('');
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarError, setCalendarError] = useState('');
  const [calendarSlots, setCalendarSlots] = useState<CalendarSlot[]>([]);

  const [forceFrom, setForceFrom] = useState('');
  const [forceTo, setForceTo] = useState('');
  const [forceLoading, setForceLoading] = useState(false);
  const [forceMessage, setForceMessage] = useState('');
  const [forceError, setForceError] = useState('');

  const [regenFeedback, setRegenFeedback] = useState('');
  const [regenLoadingSlotId, setRegenLoadingSlotId] = useState<string | null>(null);
  const [regenError, setRegenError] = useState('');
  const [publishLoadingSlotId, setPublishLoadingSlotId] = useState<string | null>(null);
  const [publishError, setPublishError] = useState('');

  const [activeTab, setActiveTab] = useState<EvolutionTab>('launch');
  const [channelsLoading, setChannelsLoading] = useState(false);
  const [channelsError, setChannelsError] = useState('');
  const [channels, setChannels] = useState<{ channel_id: string; slots_count: number }[]>([]);
  const [allSlots, setAllSlots] = useState<CalendarSlot[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>('');
  const [channelSummary, setChannelSummary] = useState<ChannelSummary | null>(null);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 768);
      if (window.innerWidth >= 768) setSidebarOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Восстанавливаем состояние последнего онбординга после перезагрузки страницы
  useEffect(() => {
    try {
      const storedChannelId = localStorage.getItem('evolutionAgent.channelId');
      const storedOnboard = localStorage.getItem('evolutionAgent.onboardResult');
      if (storedChannelId) {
        setChannelId(storedChannelId);
        setCalendarChannelId(storedChannelId);
      }
      if (storedOnboard) {
        const parsed = JSON.parse(storedOnboard) as OnboardResponse;
        setOnboardResult(parsed);
      }
    } catch {
      // игнорируем ошибки парсинга localStorage
    }
  }, []);

  // Автозагрузка календаря при наличии сохранённого channel_id
  useEffect(() => {
    const ch = calendarChannelId.trim();
    if (!ch) return;
    // не блокируем UI, просто пробуем подгрузить слоты
    (async () => {
      setCalendarLoading(true);
      setCalendarError('');
      try {
        const res = await evolutionApi.getCalendar(ch);
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || 'Ошибка загрузки календаря');
        }
        const data = (await res.json()) as CalendarSlot[];
        setCalendarSlots(data);
      } catch (e: any) {
        // тихо логируем в state, чтобы пользователь видел причину при первом рендере
        setCalendarError(e.message || 'Ошибка загрузки календаря');
      } finally {
        setCalendarLoading(false);
      }
    })();
    // вызываем только при первом заполнении calendarChannelId из localStorage
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calendarChannelId]);

  const handleOnboard = async () => {
    if (!channelId.trim()) {
      setOnboardError('Укажи channel_id (username или numeric id канала).');
      return;
    }
    if (!description.trim()) {
      setOnboardError('Опиши, о чём канал (description).');
      return;
    }
    setOnboardLoading(true);
    setOnboardError('');
    setOnboardResult(null);
    try {
      const res = await evolutionApi.onboard({
        channel_id: channelId.trim(),
        description: description.trim(),
        tone: tone.trim() || undefined,
        language,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Ошибка онбординга агента');
      }
      const data = (await res.json()) as OnboardResponse;
      setOnboardResult(data);
      setCalendarChannelId(data.channel_id);
      setForceMessage('Онбординг выполнен. Календарь создан на 7 дней.');
      setForceError('');
      // Сохраняем контекст онбординга для отображения после обновления страницы
      localStorage.setItem('evolutionAgent.channelId', data.channel_id);
      localStorage.setItem('evolutionAgent.onboardResult', JSON.stringify(data));
    } catch (e: any) {
      setOnboardError(e.message || 'Ошибка онбординга агента');
    } finally {
      setOnboardLoading(false);
    }
  };

  const handleLoadCalendar = async () => {
    const ch = calendarChannelId.trim() || channelId.trim();
    if (!ch) {
      setCalendarError('Сначала укажи channel_id.');
      return;
    }
    setCalendarLoading(true);
    setCalendarError('');
    try {
      const res = await evolutionApi.getCalendar(ch);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Ошибка загрузки календаря');
      }
      const data = (await res.json()) as CalendarSlot[];
      setCalendarSlots(data);
    } catch (e: any) {
      setCalendarError(e.message || 'Ошибка загрузки календаря');
    } finally {
      setCalendarLoading(false);
    }
  };

  const handleForceRun = async () => {
    const ch = calendarChannelId.trim() || channelId.trim();
    if (!ch) {
      setForceError('Сначала укажи channel_id.');
      return;
    }
    if (!forceFrom || !forceTo) {
      setForceError('Укажи интервал from / to.');
      return;
    }
    setForceLoading(true);
    setForceError('');
    setForceMessage('');
    try {
      const res = await evolutionApi.forceRun({
        channel_id: ch,
        from_dt: new Date(forceFrom).toISOString(),
        to_dt: new Date(forceTo).toISOString(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || 'Ошибка принудительного запуска');
      }
      setForceMessage(data.message || 'Принудительный запуск выполнен.');
      // Обновляем календарь после force-run
      handleLoadCalendar();
    } catch (e: any) {
      setForceError(e.message || 'Ошибка принудительного запуска');
    } finally {
      setForceLoading(false);
    }
  };

  const handleRegenerate = async (slotId: string) => {
    setRegenError('');
    setRegenLoadingSlotId(slotId);
    try {
      const res = await evolutionApi.regenerateSlot(slotId, regenFeedback.trim() || undefined);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || 'Ошибка регенерации слота');
      }
      // После регенерации обновляем календарь
      handleLoadCalendar();
      setRegenFeedback('');
    } catch (e: any) {
      setRegenError(e.message || 'Ошибка регенерации слота');
    } finally {
      setRegenLoadingSlotId(null);
    }
  };

  const handlePublishNow = async (slotId: string) => {
    setPublishError('');
    setPublishLoadingSlotId(slotId);
    try {
      const res = await evolutionApi.publishNow(slotId);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || 'Ошибка немедленной публикации');
      }
      // После публикации обновляем календарь
      handleLoadCalendar();
    } catch (e: any) {
      setPublishError(e.message || 'Ошибка немедленной публикации');
    } finally {
      setPublishLoadingSlotId(null);
    }
  };

  const calendarStats = useMemo(() => {
    const total = calendarSlots.length;
    const byStatus = calendarSlots.reduce<Record<string, number>>((acc, s) => {
      const key = (s.status || '').toLowerCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    return { total, byStatus };
  }, [calendarSlots]);

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar isOpen={isDesktop || isSidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col min-h-screen">
        <Header title="ИИ-агент для Telegram" onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 p-4 md:p-8 flex flex-col gap-8 max-w-6xl mx-auto w-full">
          {/* Блок онбординга */}
          <section className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 flex flex-col gap-4">
            <h2 className="text-lg font-semibold">1. Онбординг агента</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Укажи канал и опиши, как агент должен вести его. Для корректной работы сначала подключи Telegram в разделе
              «Интеграции» и добавь канал/группу.
            </p>
            {onboardError && <div className="text-red-500 text-sm">{onboardError}</div>}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Telegram channel_id</label>
                <input
                  type="text"
                  className="border rounded px-3 py-2 bg-white dark:bg-gray-900"
                  placeholder="@my_channel или numeric id"
                  value={channelId}
                  onChange={(e) => setChannelId(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Тон</label>
                <input
                  type="text"
                  className="border rounded px-3 py-2 bg-white dark:bg-gray-900"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <label className="text-sm font-medium">Описание канала / задачи</label>
                <textarea
                  className="border rounded px-3 py-2 bg-white dark:bg-gray-900 min-h-[80px]"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Язык</label>
                <select
                  className="border rounded px-3 py-2 bg-white dark:bg-gray-900"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as 'ru' | 'en')}
                >
                  <option value="ru">Русский</option>
                  <option value="en">English</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-4 mt-2">
              <button
                onClick={handleOnboard}
                disabled={onboardLoading}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-60"
              >
                {onboardLoading ? 'Создаём агента…' : 'Создать/пересоздать стратегию'}
              </button>
              {onboardResult && (
                <div className="text-sm text-green-600">
                  Стратегия создана: <span className="font-mono">{onboardResult.strategy_id}</span>
                </div>
              )}
            </div>
          </section>

          {/* Календарь и управление слотами */}
          <section className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 flex flex-col gap-4">
            <h2 className="text-lg font-semibold">2. Календарь и управление слотами</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Канал для календаря</label>
                <input
                  type="text"
                  className="border rounded px-3 py-2 bg-white dark:bg-gray-900"
                  placeholder="Оставь пустым, чтобы использовать channel_id из онбординга"
                  value={calendarChannelId}
                  onChange={(e) => setCalendarChannelId(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">From (UTC)</label>
                <input
                  type="datetime-local"
                  className="border rounded px-3 py-2 bg-white dark:bg-gray-900"
                  value={forceFrom}
                  onChange={(e) => setForceFrom(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">To (UTC)</label>
                <input
                  type="datetime-local"
                  className="border rounded px-3 py-2 bg-white dark:bg-gray-900"
                  value={forceTo}
                  onChange={(e) => setForceTo(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-4 mt-2">
              <button
                onClick={handleLoadCalendar}
                disabled={calendarLoading}
                className="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-60"
              >
                {calendarLoading ? 'Загружаем календарь…' : 'Загрузить календарь'}
              </button>
              <button
                onClick={handleForceRun}
                disabled={forceLoading}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-60"
              >
                {forceLoading ? 'Запускаем…' : 'Принудительно сгенерировать в интервале'}
              </button>
              {forceMessage && <div className="text-sm text-green-600">{forceMessage}</div>}
              {forceError && <div className="text-sm text-red-500">{forceError}</div>}
              {calendarError && <div className="text-sm text-red-500">{calendarError}</div>}
              {regenError && <div className="text-sm text-red-500">{regenError}</div>}
              {publishError && <div className="text-sm text-red-500">{publishError}</div>}
            </div>

            <div className="mt-4">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 mb-2">
                <h3 className="text-md font-semibold">Слоты</h3>
                {calendarStats.total > 0 && (
                  <div className="text-xs text-gray-600 dark:text-gray-400 flex flex-wrap gap-2">
                    <span>Всего: {calendarStats.total}</span>
                    <span>| PLANNED: {calendarStats.byStatus.planned || 0}</span>
                    <span>| PROCESSING: {calendarStats.byStatus.processing || 0}</span>
                    <span>| READY: {calendarStats.byStatus.ready || 0}</span>
                    <span>| PUBLISHED: {calendarStats.byStatus.published || 0}</span>
                    <span>| FAILED: {calendarStats.byStatus.failed || 0}</span>
                  </div>
                )}
              </div>
              {calendarLoading ? (
                <div className="text-gray-400">Загрузка календаря…</div>
              ) : calendarSlots.length === 0 ? (
                <div className="text-gray-500 text-sm">Слотов пока нет. Выполни онбординг или выбери другой канал.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-700">
                        <th className="text-left py-2 pr-4">Дата/время (UTC)</th>
                        <th className="text-left py-2 pr-4">Статус</th>
                        <th className="text-left py-2 pr-4">Pillar</th>
                        <th className="text-left py-2 pr-4">Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {calendarSlots.map((slot) => (
                        <tr
                          key={slot.slot_id}
                          className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-900"
                        >
                          <td className="py-2 pr-4">
                            {new Date(slot.dt).toLocaleString(undefined, {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </td>
                          <td className="py-2 pr-4">
                                <span
                              className={`
                                inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
                                ${(() => {
                                  const st = (slot.status || '').toLowerCase();
                                  if (st === 'ready') return 'bg-blue-100 text-blue-800';
                                  if (st === 'published') return 'bg-green-100 text-green-800';
                                  if (st === 'failed') return 'bg-red-100 text-red-800';
                                  if (st === 'processing') return 'bg-yellow-100 text-yellow-800';
                                  return 'bg-gray-100 text-gray-800';
                                })()}
                              `}
                            >
                              {slot.status}
                            </span>
                          </td>
                          <td className="py-2 pr-4">{slot.pillar || '—'}</td>
                          <td className="py-2 pr-4">
                            <div className="flex flex-col gap-2">
                              <div className="flex flex-wrap gap-2">
                                {(slot.status || '').toLowerCase() === 'planned' && (
                                  <button
                                    onClick={() => handlePublishNow(slot.slot_id)}
                                    disabled={publishLoadingSlotId === slot.slot_id}
                                    className="bg-blue-600 text-white px-3 py-1 rounded text-xs hover:bg-blue-700 disabled:opacity-60"
                                  >
                                    {publishLoadingSlotId === slot.slot_id ? 'Публикуем…' : 'Опубликовать сейчас'}
                                  </button>
                                )}
                                <button
                                  onClick={() => handleRegenerate(slot.slot_id)}
                                  disabled={regenLoadingSlotId === slot.slot_id}
                                  className="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 px-3 py-1 rounded text-xs hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-60 text-left"
                                >
                                  {regenLoadingSlotId === slot.slot_id ? 'Регенерация…' : 'Регенерировать с фидбеком'}
                                </button>
                              </div>
                              <textarea
                                className="border rounded px-2 py-1 text-xs bg-white dark:bg-gray-900"
                                placeholder="Опциональный фидбек для этого и следующих слотов"
                                value={regenFeedback}
                                onChange={(e) => setRegenFeedback(e.target.value)}
                              />
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default EvolutionAgent;

