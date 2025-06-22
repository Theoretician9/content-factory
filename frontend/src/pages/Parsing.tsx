import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { parsingApi } from '../api';
import Loader from '../components/Loader';
import ErrorMessage from '../components/ErrorMessage';
import Button from '../components/Button';

interface ParseTask {
  id: string;
  user_id: number;
  platform: 'telegram' | 'instagram' | 'whatsapp';
  link: string;
  task_type: string;
  priority: 'low' | 'normal' | 'high';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused';
  progress: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  error_message?: string;
  result_count?: number;
}

interface ParseResult {
  id: string;
  task_id: string;
  platform: string;
  platform_id: string;
  username?: string;
  display_name: string;
  platform_specific_data: any;
  created_at: string;
}

interface CommunitySearchResult {
  platform: string;
  platform_id: string;
  title: string;
  username?: string;
  description?: string;
  members_count?: number;
  link: string;
  platform_specific_data?: any;
}

const Parsing = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 768);
  
  // Основное состояние
  const [activeTab, setActiveTab] = useState<'create' | 'tasks' | 'search' | 'stats'>('create');
  const [selectedPlatform, setSelectedPlatform] = useState<'telegram' | 'instagram' | 'whatsapp'>('telegram');
  
  // Задачи парсинга
  const [tasks, setTasks] = useState<ParseTask[]>([]);
  const [tasksFilter, setTasksFilter] = useState({
    platform: '',
    status: '',
    page: 1,
    limit: 20
  });
  
  // Создание задачи
  const [createForm, setCreateForm] = useState({
    platform: 'telegram' as const,
    links: [''],
    priority: 'normal' as const,
    settings: {
      max_depth: 10000,
      include_media: true,
      date_from: '',
      date_to: ''
    }
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  
  // Результаты задачи
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [taskResults, setTaskResults] = useState<ParseResult[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);
  
  // Поиск сообществ
  const [searchForm, setSearchForm] = useState({
    platform: 'telegram' as const,
    query: '',
    offset: 0,
    limit: 100
  });
  const [searchResults, setSearchResults] = useState<CommunitySearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 768);
      if (window.innerWidth >= 768) setSidebarOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    loadTasks();
  }, [tasksFilter]);

  const loadTasks = async () => {
    setLoading(true);
    setError('');
    
    try {
      const res = await parsingApi.tasks.list(tasksFilter);
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || data);
      } else {
        setError('Ошибка загрузки задач парсинга');
      }
    } catch (err) {
      setError('Ошибка сети при загрузке задач');
      console.error('Error loading tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTask = async () => {
    if (!createForm.links[0]?.trim()) {
      setCreateError('Введите хотя бы одну ссылку');
      return;
    }

    // Валидация ссылок по платформе
    const validLinks = createForm.links.filter(link => link.trim());
    for (const link of validLinks) {
      if (createForm.platform === 'telegram') {
        if (!link.includes('t.me/') && !link.startsWith('@')) {
          setCreateError('Неверный формат Telegram ссылки. Используйте t.me/username или @username');
          return;
        }
      } else if (createForm.platform === 'instagram') {
        if (!link.includes('instagram.com/')) {
          setCreateError('Неверный формат Instagram ссылки');
          return;
        }
      } else if (createForm.platform === 'whatsapp') {
        if (!link.includes('wa.me/') && !link.includes('whatsapp.com/')) {
          setCreateError('Неверный формат WhatsApp ссылки');
          return;
        }
      }
    }

    setCreating(true);
    setCreateError('');

    try {
      const res = await parsingApi.tasks.create({
        platform: createForm.platform,
        links: validLinks,
        priority: createForm.priority,
        settings: createForm.settings
      });

      if (res.ok) {
        setCreateForm(prev => ({ ...prev, links: [''] }));
        setCreateError('');
        loadTasks(); // Перезагружаем список задач
        setActiveTab('tasks'); // Переходим на вкладку задач
      } else {
        const error = await res.json();
        setCreateError(error.detail || 'Ошибка создания задачи');
      }
    } catch (err) {
      setCreateError('Ошибка сети');
    } finally {
      setCreating(false);
    }
  };

  const handleTaskAction = async (taskId: string, action: 'pause' | 'resume' | 'delete') => {
    try {
      let res;
      if (action === 'pause') {
        res = await parsingApi.tasks.pause(taskId);
      } else if (action === 'resume') {
        res = await parsingApi.tasks.resume(taskId);
      } else if (action === 'delete') {
        if (!confirm('Вы уверены, что хотите удалить эту задачу?')) return;
        res = await parsingApi.tasks.delete(taskId);
      }

      if (res?.ok) {
        loadTasks();
      }
    } catch (err) {
      console.error(`Error ${action} task:`, err);
    }
  };

  const handleViewResults = async (taskId: string) => {
    setSelectedTaskId(taskId);
    setResultsLoading(true);
    
    try {
      const res = await parsingApi.results.get(taskId);
      if (res.ok) {
        const data = await res.json();
        setTaskResults(data.results || data);
      }
    } catch (err) {
      console.error('Error loading results:', err);
    } finally {
      setResultsLoading(false);
    }
  };

  const handleExportResults = async (taskId: string, format: 'json' | 'csv' | 'ndjson') => {
    try {
      const res = await parsingApi.results.export(taskId, format);
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `parsing_results_${taskId}.${format}`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Error exporting results:', err);
    }
  };

  const handleSearchCommunities = async () => {
    if (!searchForm.query.trim()) {
      setSearchError('Введите поисковый запрос');
      return;
    }

    setSearching(true);
    setSearchError('');

    try {
      const res = await parsingApi.search.communities({
        platform: searchForm.platform,
        query: searchForm.query.trim(),
        offset: searchForm.offset,
        limit: searchForm.limit
      });

      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || data);
      } else {
        const error = await res.json();
        setSearchError(error.detail || 'Ошибка поиска');
      }
    } catch (err) {
      setSearchError('Ошибка сети');
    } finally {
      setSearching(false);
    }
  };

  const addLinkField = () => {
    setCreateForm(prev => ({
      ...prev,
      links: [...prev.links, '']
    }));
  };

  const removeLinkField = (index: number) => {
    setCreateForm(prev => ({
      ...prev,
      links: prev.links.filter((_, i) => i !== index)
    }));
  };

  const updateLink = (index: number, value: string) => {
    setCreateForm(prev => ({
      ...prev,
      links: prev.links.map((link, i) => i === index ? value : link)
    }));
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100';
      case 'running': return 'text-blue-600 bg-blue-100';
      case 'pending': return 'text-yellow-600 bg-yellow-100';
      case 'paused': return 'text-orange-600 bg-orange-100';
      case 'failed': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getPlatformIcon = (platform: string) => {
    switch (platform) {
      case 'telegram': return '📱';
      case 'instagram': return '📸';
      case 'whatsapp': return '💬';
      default: return '🌐';
    }
  };

  if (loading && tasks.length === 0) {
    return (
      <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="flex items-center justify-center w-full">
          <Loader />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar isOpen={isDesktop || isSidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col min-h-screen">
        <Header title="Парсинг" onMenuClick={() => setSidebarOpen(true)} />
        
        <main className="flex-1 p-4 md:p-8">
          {error && <ErrorMessage message={error} />}
          
          {/* Вкладки */}
          <div className="mb-6 border-b border-gray-200 dark:border-gray-700">
            <nav className="flex space-x-8">
              {[
                { key: 'create', label: 'Создать задачу', icon: '➕' },
                { key: 'tasks', label: 'Задачи парсинга', icon: '📋' },
                { key: 'search', label: 'Поиск сообществ', icon: '🔍' },
                { key: 'stats', label: 'Статистика', icon: '📊' }
              ].map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as any)}
                  className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                    activeTab === tab.key
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <span>{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Контент вкладок */}
          
          {/* Создание задачи */}
          {activeTab === 'create' && (
            <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
              <h3 className="text-xl font-bold mb-6">Создать задачу парсинга</h3>
              
              {/* Выбор платформы */}
              <div className="mb-6">
                <label className="block text-sm font-medium mb-3">Платформа</label>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { key: 'telegram', name: 'Telegram', icon: '📱', available: true },
                    { key: 'instagram', name: 'Instagram', icon: '📸', available: false },
                    { key: 'whatsapp', name: 'WhatsApp', icon: '💬', available: false }
                  ].map(platform => (
                    <button
                      key={platform.key}
                      onClick={() => platform.available && setCreateForm(prev => ({ ...prev, platform: platform.key as any }))}
                      className={`
                        relative flex flex-col items-center p-4 rounded-lg border-2 transition-all duration-200
                        ${createForm.platform === platform.key 
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' 
                          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                        }
                        ${!platform.available ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-md'}
                      `}
                      disabled={!platform.available}
                    >
                      <span className="text-2xl mb-2">{platform.icon}</span>
                      <span className="text-sm font-medium">{platform.name}</span>
                      {!platform.available && (
                        <div className="absolute -top-1 -right-1 bg-yellow-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                          Soon
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Ссылки для парсинга */}
              <div className="mb-6">
                <label className="block text-sm font-medium mb-2">Ссылки для парсинга</label>
                {createForm.links.map((link, index) => (
                  <div key={index} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      placeholder={
                        createForm.platform === 'telegram' ? 't.me/username или @username' :
                        createForm.platform === 'instagram' ? 'instagram.com/username' :
                        'whatsapp.com/invite/xxx'
                      }
                      value={link}
                      onChange={(e) => updateLink(index, e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    {createForm.links.length > 1 && (
                      <button
                        onClick={() => removeLinkField(index)}
                        className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-md"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
                <button
                  onClick={addLinkField}
                  className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                >
                  + Добавить ссылку
                </button>
              </div>

              {/* Настройки */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium mb-2">Приоритет</label>
                  <select
                    value={createForm.priority}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, priority: e.target.value as any }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="low">Низкий</option>
                    <option value="normal">Обычный</option>
                    <option value="high">Высокий</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Максимальная глубина</label>
                  <input
                    type="number"
                    min="100"
                    max="50000"
                    value={createForm.settings.max_depth}
                    onChange={(e) => setCreateForm(prev => ({ 
                      ...prev, 
                      settings: { ...prev.settings, max_depth: parseInt(e.target.value) }
                    }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {createError && <ErrorMessage message={createError} />}
              
              <Button onClick={handleCreateTask} loading={creating}>
                Создать задачу парсинга
              </Button>
            </div>
          )}

          {/* Список задач */}
          {activeTab === 'tasks' && (
            <div className="space-y-6">
              {/* Фильтры */}
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Платформа</label>
                    <select
                      value={tasksFilter.platform}
                      onChange={(e) => setTasksFilter(prev => ({ ...prev, platform: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Все платформы</option>
                      <option value="telegram">Telegram</option>
                      <option value="instagram">Instagram</option>
                      <option value="whatsapp">WhatsApp</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Статус</label>
                    <select
                      value={tasksFilter.status}
                      onChange={(e) => setTasksFilter(prev => ({ ...prev, status: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Все статусы</option>
                      <option value="pending">Ожидает</option>
                      <option value="running">Выполняется</option>
                      <option value="completed">Завершен</option>
                      <option value="failed">Ошибка</option>
                      <option value="paused">Приостановлен</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Таблица задач */}
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Задача
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Платформа
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Статус
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Прогресс
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Создана
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Действия
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {tasks.map((task) => (
                        <tr key={task.id}>
                          <td className="px-6 py-4">
                            <div className="flex flex-col">
                              <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                {task.link}
                              </div>
                              <div className="text-sm text-gray-500 dark:text-gray-400">
                                {task.task_type} • {task.priority}
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center">
                              <span className="mr-2">{getPlatformIcon(task.platform)}</span>
                              <span className="text-sm text-gray-900 dark:text-gray-100 capitalize">
                                {task.platform}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(task.status)}`}>
                              {task.status}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center">
                              <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                                <div 
                                  className="bg-blue-600 h-2 rounded-full" 
                                  style={{ width: `${task.progress}%` }}
                                ></div>
                              </div>
                              <span className="text-sm text-gray-900 dark:text-gray-100">
                                {task.progress}%
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100">
                            {formatDate(task.created_at)}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center space-x-2">
                              {task.status === 'running' && (
                                <button
                                  onClick={() => handleTaskAction(task.id, 'pause')}
                                  className="text-orange-600 hover:text-orange-700 text-sm"
                                >
                                  ⏸️
                                </button>
                              )}
                              {task.status === 'paused' && (
                                <button
                                  onClick={() => handleTaskAction(task.id, 'resume')}
                                  className="text-green-600 hover:text-green-700 text-sm"
                                >
                                  ▶️
                                </button>
                              )}
                              {task.status === 'completed' && (
                                <>
                                  <button
                                    onClick={() => handleViewResults(task.id)}
                                    className="text-blue-600 hover:text-blue-700 text-sm"
                                  >
                                    👁️
                                  </button>
                                  <button
                                    onClick={() => handleExportResults(task.id, 'json')}
                                    className="text-green-600 hover:text-green-700 text-sm"
                                  >
                                    📥
                                  </button>
                                </>
                              )}
                              <button
                                onClick={() => handleTaskAction(task.id, 'delete')}
                                className="text-red-600 hover:text-red-700 text-sm"
                              >
                                🗑️
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Результаты задачи */}
              {selectedTaskId && (
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-lg font-semibold">Результаты парсинга</h4>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleExportResults(selectedTaskId, 'json')}
                        className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200"
                      >
                        JSON
                      </button>
                      <button
                        onClick={() => handleExportResults(selectedTaskId, 'csv')}
                        className="px-3 py-1 text-sm bg-green-100 text-green-700 rounded-md hover:bg-green-200"
                      >
                        CSV
                      </button>
                      <button
                        onClick={() => setSelectedTaskId('')}
                        className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
                      >
                        Закрыть
                      </button>
                    </div>
                  </div>
                  
                  {resultsLoading ? (
                    <Loader />
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left py-2">Платформа</th>
                            <th className="text-left py-2">ID</th>
                            <th className="text-left py-2">Username</th>
                            <th className="text-left py-2">Имя</th>
                            <th className="text-left py-2">Дата</th>
                          </tr>
                        </thead>
                        <tbody>
                          {taskResults.map((result) => (
                            <tr key={result.id} className="border-b">
                              <td className="py-2">
                                <span className="mr-1">{getPlatformIcon(result.platform)}</span>
                                {result.platform}
                              </td>
                              <td className="py-2">{result.platform_id}</td>
                              <td className="py-2">{result.username || '-'}</td>
                              <td className="py-2">{result.display_name}</td>
                              <td className="py-2">{formatDate(result.created_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Поиск сообществ */}
          {activeTab === 'search' && (
            <div className="space-y-6">
              <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
                <h3 className="text-lg font-semibold mb-4">Поиск сообществ</h3>
                
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Платформа</label>
                    <select
                      value={searchForm.platform}
                      onChange={(e) => setSearchForm(prev => ({ ...prev, platform: e.target.value as any }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="telegram">Telegram</option>
                      <option value="instagram" disabled>Instagram (скоро)</option>
                      <option value="whatsapp" disabled>WhatsApp (скоро)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Поисковый запрос</label>
                    <input
                      type="text"
                      placeholder="Введите ключевые слова..."
                      value={searchForm.query}
                      onChange={(e) => setSearchForm(prev => ({ ...prev, query: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div className="flex items-end">
                    <Button onClick={handleSearchCommunities} loading={searching}>
                      Поиск
                    </Button>
                  </div>
                </div>

                {searchError && <ErrorMessage message={searchError} />}
              </div>

              {/* Результаты поиска */}
              {searchResults.length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                    <h4 className="text-lg font-semibold">Найденные сообщества ({searchResults.length})</h4>
                  </div>
                  <div className="divide-y divide-gray-200 dark:divide-gray-700">
                    {searchResults.map((result, index) => (
                      <div key={index} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center mb-2">
                              <span className="mr-2">{getPlatformIcon(result.platform)}</span>
                              <h5 className="font-medium text-gray-900 dark:text-gray-100">
                                {result.title}
                              </h5>
                              {result.username && (
                                <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
                                  @{result.username}
                                </span>
                              )}
                            </div>
                            {result.description && (
                              <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">
                                {result.description}
                              </p>
                            )}
                            <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                              {result.members_count && (
                                <span className="mr-4">👥 {result.members_count.toLocaleString()}</span>
                              )}
                              <a
                                href={result.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:text-blue-700"
                              >
                                Открыть ↗
                              </a>
                            </div>
                          </div>
                          <button
                            onClick={() => {
                              setCreateForm(prev => ({
                                ...prev,
                                platform: result.platform as any,
                                links: [result.link]
                              }));
                              setActiveTab('create');
                            }}
                            className="ml-4 px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200"
                          >
                            Парсить
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Статистика */}
          {activeTab === 'stats' && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold mb-4">Статистика парсинга</h3>
              <p className="text-gray-600 dark:text-gray-400">
                Статистика будет доступна после создания первых задач парсинга.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default Parsing; 