import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

// Типы данных
interface InviteTask {
  id: number;
  name: string;
  description?: string;
  platform: string;
  status: 'PENDING' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  priority: 'HIGH' | 'NORMAL' | 'LOW';
  target_count: number;
  completed_count: number;
  failed_count: number;
  created_at: string;
  updated_at: string;
}

interface TaskStats {
  task_id: number;
  task_name: string;
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
}

const Mailing: React.FC = () => {
  const { t } = useTranslation();
  
  // Состояние компонента
  const [tasks, setTasks] = useState<InviteTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [selectedTask, setSelectedTask] = useState<InviteTask | null>(null);
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null);
  const [activeTab, setActiveTab] = useState<'tasks' | 'create' | 'import' | 'stats'>('tasks');
  
  // Форма создания задачи
  const [newTask, setNewTask] = useState({
    name: '',
    description: '',
    platform: 'telegram',
    priority: 'NORMAL' as const,
    invite_message: '',
    delay_between_invites: 5
  });
  
  // Состояние для импорта файлов
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importProgress, setImportProgress] = useState<{
    importing: boolean;
    result?: any;
  }>({ importing: false });

  // Загрузка задач при монтировании компонента
  useEffect(() => {
    loadTasks();
  }, []);

  // API функции
  const apiCall = async (endpoint: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`/api/invite${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  };

  const loadTasks = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiCall('/tasks/');
      setTasks(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки задач');
    } finally {
      setLoading(false);
    }
  };

  const createTask = async () => {
    if (!newTask.name.trim()) {
      setError('Введите название задачи');
      return;
    }

    setLoading(true);
    try {
      await apiCall('/tasks/', {
        method: 'POST',
        body: JSON.stringify(newTask),
      });
      
      setNewTask({
        name: '',
        description: '',
        platform: 'telegram',
        priority: 'NORMAL',
        invite_message: '',
        delay_between_invites: 5
      });
      
      await loadTasks();
      setActiveTab('tasks');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка создания задачи');
    } finally {
      setLoading(false);
    }
  };

  const executeTask = async (taskId: number) => {
    try {
      await apiCall(`/tasks/${taskId}/execute`, { method: 'POST' });
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка запуска задачи');
    }
  };

  const pauseTask = async (taskId: number) => {
    try {
      await apiCall(`/tasks/${taskId}/pause`, { method: 'POST' });
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка приостановки задачи');
    }
  };

  const resumeTask = async (taskId: number) => {
    try {
      await apiCall(`/tasks/${taskId}/resume`, { method: 'POST' });
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка возобновления задачи');
    }
  };

  const loadTaskStats = async (taskId: number) => {
    try {
      const stats = await apiCall(`/tasks/${taskId}/stats`);
      setTaskStats(stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки статистики');
    }
  };

  const handleFileImport = async (taskId: number) => {
    if (!importFile) {
      setError('Выберите файл для импорта');
      return;
    }

    setImportProgress({ importing: true });
    const formData = new FormData();
    formData.append('file', importFile);
    formData.append('source_name', `import_${Date.now()}`);

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/invite/tasks/${taskId}/import/file`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Import failed: ${response.status}`);
      }

      const result = await response.json();
      setImportProgress({ importing: false, result });
      setImportFile(null);
      await loadTasks();
    } catch (err) {
      setImportProgress({ importing: false });
      setError(err instanceof Error ? err.message : 'Ошибка импорта файла');
    }
  };

  // Функции для статусов и стилей
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'RUNNING': return 'text-blue-600 bg-blue-100';
      case 'COMPLETED': return 'text-green-600 bg-green-100';
      case 'FAILED': return 'text-red-600 bg-red-100';
      case 'PAUSED': return 'text-yellow-600 bg-yellow-100';
      case 'CANCELLED': return 'text-gray-600 bg-gray-100';
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

  const getProgressPercentage = (task: InviteTask) => {
    if (task.target_count === 0) return 0;
    return Math.round(((task.completed_count + task.failed_count) / task.target_count) * 100);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Заголовок */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            {t('Массовые приглашения')}
          </h1>
          <p className="text-gray-600">
            {t('Управление задачами приглашений в мессенджеры')}
          </p>
        </div>

        {/* Сообщения об ошибках */}
        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
            {error}
            <button
              onClick={() => setError('')}
              className="float-right text-red-500 hover:text-red-700"
            >
              ×
            </button>
          </div>
        )}

        {/* Навигационные табы */}
        <div className="mb-6">
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
                className={`flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  activeTab === tab.key
                    ? 'bg-blue-100 text-blue-700 border-b-2 border-blue-500'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Контент табов */}
        <div className="bg-white rounded-lg shadow">
          {/* Таб: Список задач */}
          {activeTab === 'tasks' && (
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold">Список задач</h2>
                <button
                  onClick={loadTasks}
                  disabled={loading}
                  className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? 'Загрузка...' : 'Обновить'}
                </button>
              </div>

              {/* Таблица задач */}
              <div className="overflow-x-auto">
                <table className="min-w-full table-auto">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Название
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Платформа
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Статус
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Прогресс
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Приоритет
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Действия
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {tasks.map(task => (
                      <tr key={task.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {task.name}
                            </div>
                            {task.description && (
                              <div className="text-sm text-gray-500">
                                {task.description}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {task.platform}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                            {task.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-600 h-2 rounded-full"
                              style={{ width: `${getProgressPercentage(task)}%` }}
                            ></div>
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            {task.completed_count + task.failed_count} / {task.target_count}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getPriorityColor(task.priority)}`}>
                            {task.priority}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                          {task.status === 'PENDING' && (
                            <button
                              onClick={() => executeTask(task.id)}
                              className="text-green-600 hover:text-green-900"
                            >
                              ▶ Запустить
                            </button>
                          )}
                          {task.status === 'RUNNING' && (
                            <button
                              onClick={() => pauseTask(task.id)}
                              className="text-yellow-600 hover:text-yellow-900"
                            >
                              ⏸ Пауза
                            </button>
                          )}
                          {task.status === 'PAUSED' && (
                            <button
                              onClick={() => resumeTask(task.id)}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              ⏯ Продолжить
                            </button>
                          )}
                          <button
                            onClick={() => {
                              setSelectedTask(task);
                              loadTaskStats(task.id);
                              setActiveTab('stats');
                            }}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            📊 Статистика
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {tasks.length === 0 && !loading && (
                  <div className="text-center py-8 text-gray-500">
                    Задач пока нет. Создайте первую задачу!
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Таб: Создание задачи */}
          {activeTab === 'create' && (
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-6">Создать новую задачу</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Название задачи *
                  </label>
                  <input
                    type="text"
                    value={newTask.name}
                    onChange={(e) => setNewTask({ ...newTask, name: e.target.value })}
                    className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Например: Приглашения в группу"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Платформа
                  </label>
                  <select
                    value={newTask.platform}
                    onChange={(e) => setNewTask({ ...newTask, platform: e.target.value })}
                    className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="telegram">Telegram</option>
                    <option value="instagram">Instagram</option>
                    <option value="whatsapp">WhatsApp</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Приоритет
                  </label>
                  <select
                    value={newTask.priority}
                    onChange={(e) => setNewTask({ ...newTask, priority: e.target.value as any })}
                    className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="HIGH">Высокий</option>
                    <option value="NORMAL">Обычный</option>
                    <option value="LOW">Низкий</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Задержка между приглашениями (сек)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={newTask.delay_between_invites}
                    onChange={(e) => setNewTask({ ...newTask, delay_between_invites: parseInt(e.target.value) })}
                    className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Описание
                  </label>
                  <textarea
                    value={newTask.description}
                    onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                    rows={3}
                    className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Описание задачи (необязательно)"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Сообщение для приглашения
                  </label>
                  <textarea
                    value={newTask.invite_message}
                    onChange={(e) => setNewTask({ ...newTask, invite_message: e.target.value })}
                    rows={4}
                    className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Привет! Приглашаю тебя в нашу группу..."
                  />
                </div>
              </div>

              <div className="mt-6 flex justify-end space-x-3">
                <button
                  onClick={() => setActiveTab('tasks')}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Отмена
                </button>
                <button
                  onClick={createTask}
                  disabled={loading || !newTask.name.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? 'Создание...' : 'Создать задачу'}
                </button>
              </div>
            </div>
          )}

          {/* Таб: Импорт данных */}
          {activeTab === 'import' && (
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-6">Импорт целевой аудитории</h2>
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Выберите задачу для импорта
                  </label>
                  <select
                    value={selectedTask?.id || ''}
                    onChange={(e) => {
                      const task = tasks.find(t => t.id === parseInt(e.target.value));
                      setSelectedTask(task || null);
                    }}
                    className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="">Выберите задачу</option>
                    {tasks.map(task => (
                      <option key={task.id} value={task.id}>
                        {task.name} ({task.platform})
                      </option>
                    ))}
                  </select>
                </div>

                {selectedTask && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Загрузить файл (CSV, JSON, TXT)
                    </label>
                    <input
                      type="file"
                      accept=".csv,.json,.txt"
                      onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                      className="w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    />
                    <p className="text-sm text-gray-500 mt-2">
                      Поддерживаемые форматы: CSV (с заголовками), JSON (массив объектов), TXT (по одному значению на строку)
                    </p>
                  </div>
                )}

                {importFile && selectedTask && (
                  <div className="flex justify-end">
                    <button
                      onClick={() => handleFileImport(selectedTask.id)}
                      disabled={importProgress.importing}
                      className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                    >
                      {importProgress.importing ? 'Импорт...' : 'Импортировать'}
                    </button>
                  </div>
                )}

                {importProgress.result && (
                  <div className="p-4 bg-green-100 border border-green-400 text-green-700 rounded-lg">
                    <h3 className="font-medium">Импорт завершен!</h3>
                    <p>Импортировано: {importProgress.result.imported_count}</p>
                    <p>Ошибок: {importProgress.result.error_count}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Таб: Статистика */}
          {activeTab === 'stats' && taskStats && (
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-6">
                Статистика: {taskStats.task_name}
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {/* Статистика по целям */}
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h3 className="font-medium text-blue-800 mb-3">Целевая аудитория</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Всего целей:</span>
                      <span className="font-medium">{taskStats.targets_statistics.total_targets}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Приглашено:</span>
                      <span className="font-medium text-green-600">{taskStats.targets_statistics.invited_targets}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Неудачно:</span>
                      <span className="font-medium text-red-600">{taskStats.targets_statistics.failed_targets}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Прогресс:</span>
                      <span className="font-medium">{taskStats.targets_statistics.progress_percentage}%</span>
                    </div>
                  </div>
                </div>

                {/* Статистика выполнения */}
                <div className="bg-green-50 p-4 rounded-lg">
                  <h3 className="font-medium text-green-800 mb-3">Выполнение</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Попыток:</span>
                      <span className="font-medium">{taskStats.execution_statistics.total_attempts}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Успешно:</span>
                      <span className="font-medium text-green-600">{taskStats.execution_statistics.successful_invites}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Rate limit:</span>
                      <span className="font-medium text-yellow-600">{taskStats.execution_statistics.rate_limited}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Время (сек):</span>
                      <span className="font-medium">{taskStats.execution_statistics.avg_execution_time}</span>
                    </div>
                  </div>
                </div>

                {/* Статус задачи */}
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h3 className="font-medium text-gray-800 mb-3">Статус</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Статус:</span>
                      <span className={`font-medium px-2 py-1 rounded text-xs ${getStatusColor(taskStats.task_status)}`}>
                        {taskStats.task_status}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Успешность:</span>
                      <span className="font-medium">{taskStats.targets_statistics.success_rate}%</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6">
                <button
                  onClick={() => setActiveTab('tasks')}
                  className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                >
                  Вернуться к задачам
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Mailing; 