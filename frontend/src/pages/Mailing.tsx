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
  priority: 'high' | 'normal' | 'low' | 'urgent';
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  created_at: string;
  updated_at: string;
  target_count?: number;
  invited_count?: number;
  failed_count?: number;
  settings?: any;
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
  const [activeTab, setActiveTab] = useState<'create' | 'tasks' | 'stats'>('tasks');
  const [tasks, setTasks] = useState<InviteTask[]>([]);
  
  // Добавляем состояние для автообновления
  const [autoRefresh, setAutoRefresh] = useState(false);
  
  // Модальное окно импорта при запуске задачи
  const [showImportModal, setShowImportModal] = useState(false);
  const [taskToStart, setTaskToStart] = useState<string | null>(null);
  const [importTab, setImportTab] = useState<'parsing' | 'file'>('parsing');
  const [selectedParseTask, setSelectedParseTask] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState('');
  const [parseTasks, setParseTasks] = useState<ParseTask[]>([]);
  
  // Задачи приглашений
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
    priority: 'normal' as const,
    settings: {
      delay_between_invites: 30,
      batch_size: 10,
      auto_add_contacts: true,
      fallback_to_messages: true
    }
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  
  // Статистика
  const [statsData, setStatsData] = useState<TaskStats | null>(null);
  const [statsError, setStatsError] = useState('');
  const [statsLoading, setStatsLoading] = useState(false);
  
  // Аккаунты
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(false);

  // Статистика и логи
  const [selectedTaskForStats, setSelectedTaskForStats] = useState<string | null>(null);
  const [executionLogs, setExecutionLogs] = useState<ExecutionLog[]>([]);

  // Проверка администраторских прав
  const [adminCheckLoading, setAdminCheckLoading] = useState(false);
  const [adminCheckResult, setAdminCheckResult] = useState<any>(null);
  const [adminCheckError, setAdminCheckError] = useState('');
  const [groupName, setGroupName] = useState('');
  
  // Выбор базы данных для задачи
  const [selectedDataSource, setSelectedDataSource] = useState<'parsing' | 'file' | ''>('');
  const [dataSourceError, setDataSourceError] = useState('');

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 768);
      if (window.innerWidth >= 768) setSidebarOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Загрузка данных только при первом рендере
  useEffect(() => {
    loadTasks();
    loadAccounts();
  }, []); // Убираем tasksFilter из зависимостей

  // Загрузка задач парсинга только при переходе на вкладку импорта
  useEffect(() => {
    if (activeTab === 'import' && parseTasks.length === 0) {
      loadParseTasks();
    }
  }, [activeTab]);

  // Деликатное Real-time обновление только прогресса активных задач
  // Временно отключено до реализации progress-stream endpoint в backend
  /* useEffect(() => {
    const activeTasksSSE = new Map<string, EventSource>();

    const activeTasks = tasks.filter(task => 
      task.status === 'pending' || task.status === 'running'
    );

    // Только если есть активные задачи
    if (activeTasks.length === 0) {
      return;
    }

    activeTasks.forEach(task => {
      if (!activeTasksSSE.has(task.id)) {
        const eventSource = new EventSource(
          `/api/invite/tasks/${task.id}/progress-stream`
        );

        eventSource.onmessage = (event) => {
          try {
            const progressData = JSON.parse(event.data);
            
            // Обновляем только конкретную задачу, избегая полного ререндера
            setTasks(prevTasks => 
              prevTasks.map(t => 
                t.id === task.id 
                  ? { 
                      ...t, 
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

    return () => {
      activeTasksSSE.forEach(eventSource => eventSource.close());
      activeTasksSSE.clear();
    };
  }, [tasks.filter(t => t.status === 'pending' || t.status === 'running').map(t => t.id).join(',')]); */

  // Убираем агрессивное автообновление каждые 15 секунд
  // Вместо этого обновление только по запросу пользователя

  // Опциональное автообновление (только если включено пользователем)
  useEffect(() => {
    if (!autoRefresh) return;

    const intervalId = setInterval(() => {
      // Тихое обновление без спиннера
      loadTasks(false);
    }, 30000); // 30 секунд вместо 15

    return () => clearInterval(intervalId);
  }, [autoRefresh]);

  const loadTasks = async (showLoadingSpinner = true) => {
    if (showLoadingSpinner) {
      setLoading(true);
    }
    setError('');
    
    try {
      const apiFilter: any = {};
      
      // Добавляем фильтры только если они установлены
      if (tasksFilter.platform) {
        apiFilter.platform = [tasksFilter.platform];
      }
      if (tasksFilter.status) {
        apiFilter.status = [tasksFilter.status];
      }
      if (tasksFilter.page) {
        apiFilter.page = tasksFilter.page;
      }
      if (tasksFilter.limit) {
        apiFilter.page_size = tasksFilter.limit;
      }
      
      const res = await inviteApi.tasks.list(apiFilter);
      if (res.ok) {
        const data = await res.json();
        setTasks(data.items || data.tasks || data);
      } else {
        setError('Ошибка загрузки задач приглашений');
      }
    } catch (err) {
      setError('Ошибка сети при загрузке задач');
      console.error('Error loading tasks:', err);
    } finally {
      if (showLoadingSpinner) {
        setLoading(false);
      }
    }
  };

  // Обработка изменения фильтров - деликатное обновление
  const handleFilterChange = (newFilter: Partial<typeof tasksFilter>) => {
    setTasksFilter(prev => ({ ...prev, ...newFilter }));
    // Тихое обновление без спиннера загрузки
    setTimeout(() => loadTasks(false), 300);
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
        // Обновляем задачи после успешного создания
        loadTasks(false);
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
        // Тихое обновление после успешного действия
        loadTasks(false);
      } else {
        console.error(`Error ${action} task:`, res?.statusText);
      }
    } catch (err) {
      console.error('Error handling task action:', err);
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
        setStatsData(statsData);
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
    if (!taskToStart || !selectedParseTask) {
      setImportError('Выберите источник данных');
      return;
    }

    setImporting(true);
    setImportError('');

    try {
      const res = await inviteApi.import.parsing(taskToStart, {
        parsing_task_id: selectedParseTask,
        source_name: `parsing_${selectedParseTask}`
      });

      if (res.ok) {
        const data = await res.json();
        setImportError('');
        alert(`Импорт завершен! Добавлено ${data.imported_count} записей.`);
        
        // Закрываем модальное окно и запускаем задачу
        setShowImportModal(false);
        const startRes = await inviteApi.execution.start(taskToStart);
        if (startRes.ok) {
          alert('Задача запущена!');
        }
        
        // Тихое обновление после импорта
        loadTasks(false);
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
    if (!taskToStart || !importFile) {
      setImportError('Выберите файл');
      return;
    }

    setImporting(true);
    setImportError('');

    try {
      const res = await inviteApi.import.file(taskToStart, importFile, {
        source_name: `file_${Date.now()}`
      });

      if (res.ok) {
        const data = await res.json();
        setImportError('');
        setImportFile(null);
        alert(`Импорт завершен! Добавлено ${data.imported_count} записей.`);
        
        // Закрываем модальное окно и запускаем задачу
        setShowImportModal(false);
        const startRes = await inviteApi.execution.start(taskToStart);
        if (startRes.ok) {
          alert('Задача запущена!');
        }
        
        // Тихое обновление после импорта из файла
        loadTasks(false);
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

  // Проверка администраторских прав при изменении ссылки группы
  const handleGroupLinkChange = async (groupLink: string) => {
    setCreateForm(prev => ({ ...prev, target_group_id: groupLink }));
    
    if (groupLink.trim()) {
      setAdminCheckLoading(true);
      setAdminCheckError('');
      setAdminCheckResult(null);
      setGroupName('');
      
      try {
        const res = await inviteApi.execution.checkAdminRights(groupLink.trim());
        
        if (res.ok) {
          const data = await res.json();
          setAdminCheckResult(data);
          setGroupName(data.group_name || '');
          
          if (!data.can_proceed) {
            setAdminCheckError('Ни один из ваших аккаунтов не является администратором этой группы/канала');
          }
        } else {
          const error = await res.json();
          setAdminCheckError(error.detail || 'Ошибка проверки администраторских прав');
        }
      } catch (err) {
        setAdminCheckError('Ошибка сети при проверке администраторских прав');
      } finally {
        setAdminCheckLoading(false);
      }
    } else {
      setAdminCheckResult(null);
      setAdminCheckError('');
      setGroupName('');
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
                      onChange={(e) => handleFilterChange({ platform: e.target.value })}
                      className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                    >
                      <option value="">Все платформы</option>
                      <option value="telegram">Telegram</option>
                      <option value="instagram">Instagram</option>
                      <option value="whatsapp">WhatsApp</option>
                    </select>
                    
                    <select
                      value={tasksFilter.status}
                      onChange={(e) => handleFilterChange({ status: e.target.value })}
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
                      onClick={() => loadTasks(true)}
                      disabled={loading}
                      className="px-4 py-2"
                    >
                      {loading ? 'Загрузка...' : 'Обновить'}
                    </Button>
                    
                    {/* Переключатель автообновления */}
                    <label className="flex items-center px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
                      <input
                        type="checkbox"
                        checked={autoRefresh}
                        onChange={(e) => setAutoRefresh(e.target.checked)}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded mr-2"
                      />
                      Автообновление (30с)
                    </label>
                  </div>
                </div>

                {/* Информация о режиме обновления */}
                {!autoRefresh && (
                  <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900 border-l-4 border-blue-400 dark:border-blue-600">
                    <div className="flex items-center">
                      <div className="text-blue-700 dark:text-blue-200 text-sm">
                        <span className="mr-2">ℹ️</span>
                        Автообновление отключено. Данные обновляются только вручную для удобства работы. 
                        Прогресс активных задач обновляется в реальном времени.
                      </div>
                    </div>
                  </div>
                )}

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
                              <button
                                onClick={() => handleTaskAction(task.id, 'delete')}
                                className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                                title="Удалить"
                              >
                                🗑
                              </button>
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

            {/* Вкладка: Создание задачи */}
            {activeTab === 'create' && (
              <div className="p-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-6">
                  Создать задачу приглашений
                </h2>
                
                {createError && (
                  <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
                    {createError}
                  </div>
                )}

                <div className="max-w-4xl">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    
                    {/* Основная информация */}
                    <div className="md:col-span-2">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                        Основные настройки
                      </h3>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Платформа
                      </label>
                      <select
                        value={createForm.platform}
                        onChange={(e) => setCreateForm(prev => ({ ...prev, platform: e.target.value as any }))}
                        className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                      >
                        <option value="telegram">📱 Telegram</option>
                        <option value="instagram" disabled>📸 Instagram (скоро)</option>
                        <option value="whatsapp" disabled>💬 WhatsApp (скоро)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Тип действия
                      </label>
                      <select
                        value={createForm.task_type}
                        onChange={(e) => setCreateForm(prev => ({ ...prev, task_type: e.target.value as any }))}
                        className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                      >
                        <option value="invite_to_group">Приглашения в группу/канал</option>
                        <option value="send_messages">Личные сообщения</option>
                      </select>
                    </div>

                    {/* ID группы/канала */}
                    {createForm.task_type === 'invite_to_group' && (
                      <div className="md:col-span-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          ID или ссылка группы/канала *
                        </label>
                        <input
                          type="text"
                          value={createForm.target_group_id}
                          onChange={(e) => handleGroupLinkChange(e.target.value)}
                          className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                          placeholder="@group_username, t.me/group_username или -100123456789"
                        />
                        
                        {/* Статус проверки админских прав */}
                        {adminCheckLoading && (
                          <div className="mt-2 flex items-center text-blue-600">
                            <span className="animate-spin mr-2">⏳</span>
                            Проверка прав администратора...
                          </div>
                        )}
                        
                        {adminCheckError && (
                          <div className="mt-2 p-3 bg-red-100 border border-red-400 text-red-700 rounded-lg">
                            <span className="mr-2">❌</span>{adminCheckError}
                          </div>
                        )}
                        
                        {adminCheckResult && adminCheckResult.can_proceed && (
                          <div className="mt-2 p-3 bg-green-100 border border-green-400 text-green-700 rounded-lg">
                            <div className="flex items-center mb-2">
                              <span className="mr-2">✅</span>
                              <strong>Группа найдена: {groupName}</strong>
                            </div>
                            <div className="text-sm">
                              <div>Доступных администраторов: {adminCheckResult.ready_accounts?.length || 0}</div>
                              <div>Потенциал приглашений: {adminCheckResult.estimated_capacity || 0} в день</div>
                            </div>
                            
                            {adminCheckResult.ready_accounts?.length > 0 && (
                              <div className="mt-2">
                                <div className="text-sm font-medium mb-1">Готовые аккаунты:</div>
                                <div className="space-y-1">
                                  {adminCheckResult.ready_accounts.map((acc: any) => (
                                    <div key={acc.account_id} className="text-xs bg-green-50 px-2 py-1 rounded">
                                      @{acc.username} ({acc.available_invites} приглашений доступно)
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Приоритет */}
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Приоритет выполнения
                      </label>
                      <select
                        value={createForm.priority}
                        onChange={(e) => setCreateForm(prev => ({ ...prev, priority: e.target.value as any }))}
                        className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                      >
                        <option value="high">🔴 Высокий (быстрый запуск)</option>
                        <option value="normal">🔵 Обычный (рекомендуется)</option>
                        <option value="low">⚪ Низкий (фоновый режим)</option>
                      </select>
                    </div>

                    {/* Описание */}
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Описание
                      </label>
                      <textarea
                        value={createForm.description}
                        onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
                        rows={3}
                        className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                        placeholder="Описание задачи (необязательно)"
                      />
                    </div>

                    {/* Настройки в зависимости от типа */}
                    <div className="md:col-span-2">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                        Настройки {createForm.task_type === 'invite_to_group' ? 'приглашений' : 'сообщений'}
                      </h3>
                    </div>

                    {createForm.task_type === 'invite_to_group' && (
                      <div className="md:col-span-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          Текст сообщения *
                        </label>
                        <textarea
                          value={createForm.message_template}
                          onChange={(e) => setCreateForm(prev => ({ ...prev, message_template: e.target.value }))}
                          rows={4}
                          className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                          placeholder="Привет! Хочу пригласить тебя в нашу группу..."
                        />
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                          Можно использовать переменные: {'{username}'}, {'{first_name}'}, {'{last_name}'}
                        </p>
                      </div>
                    )}

                    {/* Дополнительные настройки */}
                    <div className="md:col-span-2">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                        Дополнительные настройки
                      </h3>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Задержка между действиями (сек)
                      </label>
                      <input
                        type="number"
                        min="5"
                        max="300"
                        value={createForm.settings.delay_between_invites}
                        onChange={(e) => setCreateForm(prev => ({ 
                          ...prev, 
                          settings: { ...prev.settings, delay_between_invites: parseInt(e.target.value) }
                        }))}
                        className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                      />
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        Рекомендуется 15-30 секунд для безопасности
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Размер батча
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="50"
                        value={createForm.settings.batch_size}
                        onChange={(e) => setCreateForm(prev => ({ 
                          ...prev, 
                          settings: { ...prev.settings, batch_size: parseInt(e.target.value) }
                        }))}
                        className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                      />
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        Количество пользователей обрабатываемых одновременно
                      </p>
                    </div>

                    <div className="md:col-span-2">
                      <div className="flex flex-col space-y-3">
                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={createForm.settings.auto_add_contacts}
                            onChange={(e) => setCreateForm(prev => ({ 
                              ...prev, 
                              settings: { ...prev.settings, auto_add_contacts: e.target.checked }
                            }))}
                            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                          />
                          <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                            Автоматически добавлять в контакты (для приглашений по номеру телефона)
                          </span>
                        </label>

                        {createForm.task_type === 'invite_to_group' && (
                          <label className="flex items-center">
                            <input
                              type="checkbox"
                              checked={createForm.settings.fallback_to_messages}
                              onChange={(e) => setCreateForm(prev => ({ 
                                ...prev, 
                                settings: { ...prev.settings, fallback_to_messages: e.target.checked }
                              }))}
                              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                            />
                            <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                              Отправлять личное сообщение, если приглашение невозможно
                            </span>
                          </label>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Кнопки действий */}
                  <div className="mt-8 flex flex-col sm:flex-row gap-4">
                    <Button
                      onClick={handleCreateTask}
                      disabled={creating}
                      className="flex-1 sm:flex-none px-6 py-3"
                    >
                      {creating ? (
                        <>
                          <span className="animate-spin mr-2">⏳</span>
                          Создание...
                        </>
                      ) : (
                        <>
                          <span className="mr-2">➕</span>
                          Создать задачу
                        </>
                      )}
                    </Button>
                    
                    <button
                      type="button"
                      onClick={() => setCreateForm({
                        platform: 'telegram',
                        task_type: 'invite_to_group',
                        title: '',
                        description: '',
                        target_group_id: '',
                        message_template: '',
                        priority: 'normal',
                        settings: {
                          delay_between_invites: 30,
                          batch_size: 10,
                          auto_add_contacts: true,
                          fallback_to_messages: true
                        }
                      })}
                      className="flex-1 sm:flex-none px-6 py-3 border border-gray-300 text-gray-700 dark:text-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                    >
                      <span className="mr-2">🔄</span>
                      Сбросить
                    </button>
                  </div>

                  {/* Информационный блок */}
                  <div className="mt-8 p-4 bg-blue-50 dark:bg-blue-900 border border-blue-200 dark:border-blue-700 rounded-lg">
                    <h4 className="text-sm font-medium text-blue-900 dark:text-blue-100 mb-2">
                      💡 Важная информация
                    </h4>
                    <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1">
                      <li>• Для начала работы убедитесь, что подключили Telegram аккаунты в разделе "Интеграции"</li>
                      <li>• После создания задачи нужно импортировать целевую аудиторию во вкладке "Импорт"</li>
                      <li>• Система автоматически соблюдает лимиты платформ для безопасности</li>
                      <li>• Прогресс выполнения можно отслеживать в реальном времени во вкладке "Задачи"</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Вкладка: Статистика */}
            {activeTab === 'stats' && (
              <div className="p-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-6">
                  Статистика и аналитика
                </h2>

                {!selectedTaskForStats ? (
                  <div className="max-w-2xl">
                    <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900 border border-blue-200 dark:border-blue-700 rounded-lg">
                      <h3 className="text-lg font-medium text-blue-900 dark:text-blue-100 mb-4">
                        Выберите задачу для просмотра статистики
                      </h3>
                      <select
                        value={selectedTaskForStats}
                        onChange={(e) => setSelectedTaskForStats(e.target.value)}
                        className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                      >
                        <option value="">Выберите задачу...</option>
                        {tasks.map(task => (
                          <option key={task.id} value={task.id}>
                            {task.title} - {task.status} ({task.platform})
                          </option>
                        ))}
                      </select>
                    </div>

                    {tasks.length === 0 && (
                      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                        <div className="text-4xl mb-4">📊</div>
                        <div className="text-lg font-medium mb-2">Нет задач для анализа</div>
                        <div className="text-sm">Создайте первую задачу приглашений!</div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="max-w-6xl">
                    {statsLoading ? (
                      <div className="flex justify-center py-12">
                        <div className="animate-spin h-8 w-8 border-b-2 border-blue-600"></div>
                      </div>
                    ) : statsData ? (
                      <div className="space-y-6">
                        {/* Заголовок задачи и кнопка назад */}
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                              {statsData.task_title}
                            </h3>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                              Статус: <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(statsData.task_status)}`}>
                                {statsData.task_status}
                              </span>
                            </p>
                          </div>
                          <button
                            onClick={() => setSelectedTaskForStats('')}
                            className="px-4 py-2 text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50 dark:text-gray-400 dark:hover:text-gray-200 dark:border-gray-600 dark:hover:bg-gray-700"
                          >
                            ← Назад
                          </button>
                        </div>

                        {/* Общая статистика */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                              {statsData.targets_statistics.total_targets}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">Всего целей</div>
                          </div>
                          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                              {statsData.targets_statistics.invited_targets}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">Приглашено</div>
                          </div>
                          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                              {statsData.targets_statistics.failed_targets}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">Неудачно</div>
                          </div>
                          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                              {statsData.targets_statistics.success_rate.toFixed(1)}%
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">Успешность</div>
                          </div>
                        </div>

                        {/* Детальная статистика */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                          {/* Статистика целей */}
                          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                            <h4 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                              📋 Статистика по целям
                            </h4>
                            <div className="space-y-3">
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Ожидают:</span>
                                <span className="font-medium">{statsData.targets_statistics.pending_targets}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Приглашены:</span>
                                <span className="font-medium text-green-600">{statsData.targets_statistics.invited_targets}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Неудачно:</span>
                                <span className="font-medium text-red-600">{statsData.targets_statistics.failed_targets}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Пропущены:</span>
                                <span className="font-medium text-gray-600">{statsData.targets_statistics.skipped_targets}</span>
                              </div>
                              <div className="border-t pt-3 mt-3">
                                <div className="flex justify-between font-semibold">
                                  <span>Прогресс:</span>
                                  <span>{statsData.targets_statistics.progress_percentage.toFixed(1)}%</span>
                                </div>
                                <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2 mt-2">
                                  <div
                                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                                    style={{ width: `${statsData.targets_statistics.progress_percentage}%` }}
                                  ></div>
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Статистика выполнения */}
                          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                            <h4 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                              ⚡ Статистика выполнения
                            </h4>
                            <div className="space-y-3">
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Всего попыток:</span>
                                <span className="font-medium">{statsData.execution_statistics.total_attempts}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Успешных:</span>
                                <span className="font-medium text-green-600">{statsData.execution_statistics.successful_invites}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Неудачных:</span>
                                <span className="font-medium text-red-600">{statsData.execution_statistics.failed_invites}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Rate Limited:</span>
                                <span className="font-medium text-orange-600">{statsData.execution_statistics.rate_limited}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Flood Wait:</span>
                                <span className="font-medium text-yellow-600">{statsData.execution_statistics.flood_wait}</span>
                              </div>
                              <div className="border-t pt-3 mt-3">
                                <div className="flex justify-between">
                                  <span className="text-gray-600 dark:text-gray-400">Среднее время:</span>
                                  <span className="font-medium">{statsData.execution_statistics.avg_execution_time.toFixed(2)}с</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Логи выполнения */}
                        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                          <h4 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                            📝 Последние действия
                          </h4>
                          
                          {executionLogs.length > 0 ? (
                            <div className="overflow-x-auto">
                              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                                <thead className="bg-gray-50 dark:bg-gray-700">
                                  <tr>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Время</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Действие</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Статус</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Аккаунт</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Детали</th>
                                  </tr>
                                </thead>
                                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                  {executionLogs.slice(0, 10).map((log, index) => (
                                    <tr key={index} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                                      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                                        {formatDate(log.created_at)}
                                      </td>
                                      <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">
                                        {log.action}
                                      </td>
                                      <td className="px-4 py-3 text-sm">
                                        <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(log.status)}`}>
                                          {log.status}
                                        </span>
                                      </td>
                                      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                                        {log.account_id}
                                      </td>
                                      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                                        {typeof log.details === 'object' ? JSON.stringify(log.details).substring(0, 50) + '...' : log.details}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                              <div className="text-4xl mb-4">📋</div>
                              <div className="text-lg font-medium mb-2">Нет логов выполнения</div>
                              <div className="text-sm">Логи появятся после начала выполнения задачи</div>
                            </div>
                          )}
                        </div>

                        {/* Статистика по аккаунтам */}
                        {statsData.accounts_statistics.length > 0 && (
                          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                            <h4 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">
                              👥 Статистика по аккаунтам
                            </h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                              {statsData.accounts_statistics.map((account, index) => (
                                <div key={index} className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                                  <div className="font-medium text-gray-900 dark:text-gray-100 mb-2">
                                    {account.username || account.account_id}
                                  </div>
                                  <div className="space-y-1 text-sm">
                                    <div className="flex justify-between">
                                      <span className="text-gray-600 dark:text-gray-400">Отправлено:</span>
                                      <span className="font-medium">{account.sent || 0}</span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-600 dark:text-gray-400">Успешно:</span>
                                      <span className="font-medium text-green-600">{account.success || 0}</span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-600 dark:text-gray-400">Ошибки:</span>
                                      <span className="font-medium text-red-600">{account.errors || 0}</span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-600 dark:text-gray-400">Статус:</span>
                                      <span className={`px-1 py-0.5 rounded text-xs ${getStatusColor(account.status || 'active')}`}>
                                        {account.status || 'active'}
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                        <div className="text-4xl mb-4">❌</div>
                        <div className="text-lg font-medium mb-2">Не удалось загрузить статистику</div>
                        <div className="text-sm">Попробуйте обновить страницу</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Mailing; 