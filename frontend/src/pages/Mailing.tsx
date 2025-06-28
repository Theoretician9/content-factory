import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { inviteApi, parsingApi } from '../api';
import Loader from '../components/Loader';
import ErrorMessage from '../components/ErrorMessage';
import Button from '../components/Button';

interface InviteTask {
  id: string;
  user_id: number;
  platform: 'telegram' | 'instagram' | 'whatsapp';
  task_type: 'invite_to_group' | 'send_messages';
  title: string;
  description?: string;
  target_group_id?: string;
  message_template?: string;
  priority: 'HIGH' | 'NORMAL' | 'LOW';
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  created_at: string;
  updated_at: string;
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  target_count?: number;
  invited_count?: number;
  failed_count?: number;
  settings?: {
    delay_between_invites?: number;
    batch_size?: number;
    auto_add_contacts?: boolean;
    fallback_to_messages?: boolean;
  };
}

interface TaskStats {
  task_id: string;
  task_title: string;
  task_status: string;
  targets_statistics: {
    total_targets: number;
    pending_targets: number;
    invited_targets: number;
    failed_targets: number;
    skipped_targets: number;
    progress_percentage: number;
    success_rate: number;
  };
  execution_statistics: {
    total_attempts: number;
    successful_invites: number;
    failed_invites: number;
    rate_limited: number;
    flood_wait: number;
    avg_execution_time: number;
  };
  accounts_statistics: any[];
}

interface ExecutionLog {
  id: string;
  task_id: string;
  target_id: string;
  account_id: string;
  action: string;
  status: string;
  details: any;
  created_at: string;
}

interface Account {
  account_id: string;
  platform: string;
  username?: string;
  status: string;
  daily_invite_limit: number;
  daily_invites_used: number;
  flood_wait_until?: string;
}

interface ParseTask {
  id: string;
  platform: string;
  status: string;
  result_count: number;
  created_at: string;
  link: string;
}

const Mailing = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 768);
  
  // Основное состояние
  const [activeTab, setActiveTab] = useState<'create' | 'tasks' | 'import' | 'stats'>('tasks');
  
  // Задачи приглашений
  const [tasks, setTasks] = useState<InviteTask[]>([]);
  const [tasksFilter, setTasksFilter] = useState({
    platform: '',
    status: '',
    page: 1,
    limit: 20
  });
  
  // Создание задачи
  const [createForm, setCreateForm] = useState({
    platform: 'telegram' as const,
    task_type: 'invite_to_group' as const,
    title: '',
    description: '',
    target_group_id: '',
    message_template: '',
    priority: 'NORMAL' as const,
    settings: {
      delay_between_invites: 15,
      batch_size: 10,
      auto_add_contacts: true,
      fallback_to_messages: true
    }
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  
  // Импорт данных
  const [importTab, setImportTab] = useState<'parsing' | 'file'>('parsing');
  const [selectedTaskForImport, setSelectedTaskForImport] = useState<string>('');
  const [parseTasks, setParseTasks] = useState<ParseTask[]>([]);
  const [selectedParseTask, setSelectedParseTask] = useState<string>('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState('');
  
  // Статистика
  const [selectedTaskForStats, setSelectedTaskForStats] = useState<string>('');
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null);
  const [executionLogs, setExecutionLogs] = useState<ExecutionLog[]>([]);
  const [statsLoading, setStatsLoading] = useState(false);
  
  // Аккаунты
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(false);

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
    loadAccounts();
  }, [tasksFilter]);

  useEffect(() => {
    if (activeTab === 'import') {
      loadParseTasks();
    }
  }, [activeTab]);

  // Real-time обновление прогресса
  useEffect(() => {
    const activeTasksSSE = new Map<string, EventSource>();

    const activeTasks = tasks.filter(task => 
      task.status === 'pending' || task.status === 'running'
    );

    activeTasks.forEach(task => {
      if (!activeTasksSSE.has(task.id)) {
        const eventSource = new EventSource(
          `/api/invite/tasks/${task.id}/progress-stream`
        );

        eventSource.onmessage = (event) => {
          try {
            const progressData = JSON.parse(event.data);
            
            setTasks(prevTasks => 
              prevTasks.map(t => 
                t.id === task.id 
                  ? { ...t, 
                      progress: progressData.progress, 
                      status: progressData.status,
                      invited_count: progressData.invited_count,
                      failed_count: progressData.failed_count,
                      updated_at: progressData.timestamp 
                    }
                  : t
              )
            );

            if (['completed', 'failed', 'cancelled'].includes(progressData.status)) {
              eventSource.close();
              activeTasksSSE.delete(task.id);
            }
          } catch (err) {
            console.error('Error parsing SSE data:', err);
          }
        };

        eventSource.onerror = (error) => {
          console.error('SSE error for task', task.id, error);
          eventSource.close();
          activeTasksSSE.delete(task.id);
        };

        activeTasksSSE.set(task.id, eventSource);
      }
    });

    activeTasksSSE.forEach((eventSource, taskId) => {
      const isStillActive = activeTasks.some(task => task.id === taskId);
      if (!isStillActive) {
        eventSource.close();
        activeTasksSSE.delete(taskId);
      }
    });

    return () => {
      activeTasksSSE.forEach(eventSource => eventSource.close());
      activeTasksSSE.clear();
    };
  }, [tasks.map(t => `${t.id}:${t.status}`).join(',')]);

  // Fallback: обновление каждые 15 секунд
  useEffect(() => {
    const intervalId = setInterval(() => {
      loadTasks();
    }, 15000);

    return () => clearInterval(intervalId);
  }, [tasksFilter]);

  const loadTasks = async () => {
    setLoading(true);
    setError('');
    
    try {
      const apiFilter = {
        platform: tasksFilter.platform || undefined,
        status: tasksFilter.status || undefined,
        page: tasksFilter.page,
        limit: tasksFilter.limit
      };
      
      const res = await inviteApi.tasks.list(apiFilter as any);
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || data);
      } else {
        setError('Ошибка загрузки задач приглашений');
      }
    } catch (err) {
      setError('Ошибка сети при загрузке задач');
      console.error('Error loading tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadAccounts = async () => {
    setAccountsLoading(true);
    try {
      const res = await inviteApi.accounts();
      if (res.ok) {
        const data = await res.json();
        setAccounts(data);
      }
    } catch (err) {
      console.error('Error loading accounts:', err);
    } finally {
      setAccountsLoading(false);
    }
  };

  const loadParseTasks = async () => {
    try {
      const res = await inviteApi.parsingTasks();
      if (res.ok) {
        const data = await res.json();
        setParseTasks(data);
      }
    } catch (err) {
      console.error('Error loading parse tasks:', err);
    }
  };

  const handleCreateTask = async () => {
    if (!createForm.title.trim()) {
      setCreateError('Введите название задачи');
      return;
    }

    if (createForm.task_type === 'invite_to_group' && !createForm.target_group_id.trim()) {
      setCreateError('Укажите ID/ссылку группы или канала для приглашений');
      return;
    }

    if (createForm.task_type === 'send_messages' && !createForm.message_template.trim()) {
      setCreateError('Введите текст сообщения');
      return;
    }

    setCreating(true);
    setCreateError('');

    try {
      const res = await inviteApi.tasks.create({
        platform: createForm.platform,
        task_type: createForm.task_type,
        title: createForm.title,
        description: createForm.description || undefined,
        target_group_id: createForm.target_group_id || undefined,
        message_template: createForm.message_template || undefined,
        priority: createForm.priority,
        settings: createForm.settings
      });

      if (res.ok) {
        setCreateForm(prev => ({ ...prev, title: '', description: '', target_group_id: '', message_template: '' }));
        setCreateError('');
        loadTasks();
        setActiveTab('tasks');
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

  const handleTaskAction = async (taskId: string, action: 'start' | 'pause' | 'resume' | 'cancel' | 'delete') => {
    try {
      let res;
      if (action === 'start') {
        res = await inviteApi.execution.start(taskId);
      } else if (action === 'pause') {
        res = await inviteApi.execution.pause(taskId);
      } else if (action === 'resume') {
        res = await inviteApi.execution.resume(taskId);
      } else if (action === 'cancel') {
        if (!confirm('Вы уверены, что хотите отменить эту задачу?')) return;
        res = await inviteApi.execution.cancel(taskId);
      } else if (action === 'delete') {
        if (!confirm('Вы уверены, что хотите удалить эту задачу?')) return;
        res = await inviteApi.tasks.delete(taskId);
      }

      if (res?.ok) {
        loadTasks();
      }
    } catch (err) {
      console.error(`Error ${action} task:`, err);
    }
  };

  const handleViewStats = async (taskId: string) => {
    setSelectedTaskForStats(taskId);
    setStatsLoading(true);
    setActiveTab('stats');
    
    try {
      const [statsRes, logsRes] = await Promise.all([
        inviteApi.execution.stats(taskId),
        inviteApi.execution.logs(taskId, { limit: 50 })
      ]);
      
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setTaskStats(statsData);
      }
      
      if (logsRes.ok) {
        const logsData = await logsRes.json();
        setExecutionLogs(logsData.logs || logsData);
      }
    } catch (err) {
      console.error('Error loading stats:', err);
    } finally {
      setStatsLoading(false);
    }
  };

  const handleImportFromParsing = async () => {
    if (!selectedTaskForImport || !selectedParseTask) {
      setImportError('Выберите задачу для импорта и источник данных');
      return;
    }

    setImporting(true);
    setImportError('');

    try {
      const res = await inviteApi.import.parsing(selectedTaskForImport, {
        parsing_task_id: selectedParseTask,
        source_name: `parsing_${selectedParseTask}`
      });

      if (res.ok) {
        const result = await res.json();
        setImportError('');
        loadTasks();
        setActiveTab('tasks');
      } else {
        const error = await res.json();
        setImportError(error.detail || 'Ошибка импорта данных');
      }
    } catch (err) {
      setImportError('Ошибка сети');
    } finally {
      setImporting(false);
    }
  };

  const handleImportFromFile = async () => {
    if (!selectedTaskForImport || !importFile) {
      setImportError('Выберите задачу для импорта и файл');
      return;
    }

    setImporting(true);
    setImportError('');

    try {
      const res = await inviteApi.import.file(selectedTaskForImport, importFile, {
        source_name: `file_${Date.now()}`
      });

      if (res.ok) {
        const result = await res.json();
        setImportError('');
        setImportFile(null);
        loadTasks();
        setActiveTab('tasks');
      } else {
        const error = await res.json();
        setImportError(error.detail || 'Ошибка импорта файла');
      }
    } catch (err) {
      setImportError('Ошибка сети');
    } finally {
      setImporting(false);
    }
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
      case 'cancelled': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'HIGH': return 'text-red-600 bg-red-100';
      case 'NORMAL': return 'text-blue-600 bg-blue-100';
      case 'LOW': return 'text-gray-600 bg-gray-100';
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
        <Header title="Массовые приглашения" onMenuClick={() => setSidebarOpen(true)} />
        
        <main className="flex-1 p-4 md:p-8">
          {error && <ErrorMessage message={error} />}
          
          {/* Вкладки */}
          <div className="mb-6 border-b border-gray-200 dark:border-gray-700">
            <nav className="flex space-x-8">
              {[
                { key: 'tasks', label: 'Задачи', icon: '📋' },
                { key: 'create', label: 'Создать', icon: '➕' },
                { key: 'import', label: 'Импорт', icon: '📂' },
                { key: 'stats', label: 'Статистика', icon: '📊' }
              ].map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as any)}
                  className={`flex items-center px-3 py-2 text-sm font-medium rounded-t-md transition-colors ${
                    activeTab === tab.key
                      ? 'bg-blue-100 text-blue-700 border-b-2 border-blue-500 dark:bg-blue-900 dark:text-blue-200'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800'
                  }`}
                >
                  <span className="mr-2">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Контент вкладок */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
            
            {/* Вкладка: Список задач */}
            {activeTab === 'tasks' && (
              <div className="p-6">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                    Задачи приглашений
                  </h2>
                  
                  {/* Фильтры */}
                  <div className="flex flex-wrap gap-3">
                    <select
                      value={tasksFilter.platform}
                      onChange={(e) => setTasksFilter(prev => ({ ...prev, platform: e.target.value }))}
                      className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    >
                      <option value="">Все платформы</option>
                      <option value="telegram">Telegram</option>
                      <option value="instagram">Instagram</option>
                      <option value="whatsapp">WhatsApp</option>
                    </select>
                    
                    <select
                      value={tasksFilter.status}
                      onChange={(e) => setTasksFilter(prev => ({ ...prev, status: e.target.value }))}
                      className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    >
                      <option value="">Все статусы</option>
                      <option value="pending">Ожидает</option>
                      <option value="running">Выполняется</option>
                      <option value="paused">Приостановлена</option>
                      <option value="completed">Завершена</option>
                      <option value="failed">Ошибка</option>
                      <option value="cancelled">Отменена</option>
                    </select>
                    
                    <Button
                      onClick={loadTasks}
                      disabled={loading}
                      variant="outline"
                      className="px-4 py-2"
                    >
                      {loading ? 'Загрузка...' : 'Обновить'}
                    </Button>
                  </div>
                </div>

                {/* Таблица задач */}
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Название
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Платформа
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Тип
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Статус
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Прогресс
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Приоритет
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                          Действия
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {tasks.map(task => (
                        <tr key={task.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div>
                              <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                {task.title}
                              </div>
                              {task.description && (
                                <div className="text-sm text-gray-500 dark:text-gray-400">
                                  {task.description.substring(0, 50)}...
                                </div>
                              )}
                              <div className="text-xs text-gray-400 dark:text-gray-500">
                                {formatDate(task.created_at)}
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              <span className="mr-2">{getPlatformIcon(task.platform)}</span>
                              <span className="text-sm text-gray-900 dark:text-gray-100 capitalize">
                                {task.platform}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                              {task.task_type === 'invite_to_group' ? 'Приглашения' : 'Сообщения'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                              {task.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                              <div
                                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                                style={{ width: `${task.progress || 0}%` }}
                              ></div>
                            </div>
                            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                              {task.invited_count || 0} / {task.target_count || 0}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getPriorityColor(task.priority)}`}>
                              {task.priority}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            <div className="flex flex-wrap gap-2">
                              {task.status === 'pending' && (
                                <button
                                  onClick={() => handleTaskAction(task.id, 'start')}
                                  className="text-green-600 hover:text-green-900 dark:text-green-400 dark:hover:text-green-300"
                                  title="Запустить"
                                >
                                  ▶
                                </button>
                              )}
                              {task.status === 'running' && (
                                <button
                                  onClick={() => handleTaskAction(task.id, 'pause')}
                                  className="text-yellow-600 hover:text-yellow-900 dark:text-yellow-400 dark:hover:text-yellow-300"
                                  title="Пауза"
                                >
                                  ⏸
                                </button>
                              )}
                              {task.status === 'paused' && (
                                <button
                                  onClick={() => handleTaskAction(task.id, 'resume')}
                                  className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300"
                                  title="Продолжить"
                                >
                                  ⏯
                                </button>
                              )}
                              {(task.status === 'running' || task.status === 'pending') && (
                                <button
                                  onClick={() => handleTaskAction(task.id, 'cancel')}
                                  className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                                  title="Отменить"
                                >
                                  ⏹
                                </button>
                              )}
                              <button
                                onClick={() => handleViewStats(task.id)}
                                className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300"
                                title="Статистика"
                              >
                                📊
                              </button>
                              {task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled' ? (
                                <button
                                  onClick={() => handleTaskAction(task.id, 'delete')}
                                  className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                                  title="Удалить"
                                >
                                  🗑
                                </button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {tasks.length === 0 && !loading && (
                    <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                      <div className="text-4xl mb-4">📱</div>
                      <div className="text-lg font-medium mb-2">Задач пока нет</div>
                      <div className="text-sm">Создайте первую задачу приглашений!</div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Продолжение компонента в следующей части... */}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Mailing; 