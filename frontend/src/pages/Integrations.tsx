import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { integrationApi } from '../api';
import Loader from '../components/Loader';
import ErrorMessage from '../components/ErrorMessage';
import Button from '../components/Button';

interface TelegramAccount {
  id: string;
  created_at: string;
  updated_at: string;
  user_id: number;
  phone: string;
  session_metadata: any;
  is_active: boolean;
}

interface IntegrationLog {
  id: string;
  created_at: string;
  updated_at: string;
  user_id: number;
  integration_type: string;
  action: string;
  status: string;
  details: any;
  error_message?: string;
}

interface ErrorStats {
  total_actions: number;
  error_count: number;
  success_count: number;
  error_rate: number;
  period_days: number;
}

const Integrations = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 768);
  
  // Telegram состояние
  const [telegramAccounts, setTelegramAccounts] = useState<TelegramAccount[]>([]);
  const [telegramLogs, setTelegramLogs] = useState<IntegrationLog[]>([]);
  const [errorStats, setErrorStats] = useState<ErrorStats | null>(null);
  const [activeTab, setActiveTab] = useState<'accounts' | 'logs' | 'stats'>('accounts');
  
  // Подключение аккаунта
  const [connectForm, setConnectForm] = useState({
    phone: '',
    code: '',
    password: '',
    step: 'phone' // phone, code, password, success
  });
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState('');
  const [qrCode, setQrCode] = useState('');

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 768);
      if (window.innerWidth >= 768) setSidebarOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError('');
    
    try {
      // Загружаем данные параллельно
      const [accountsRes, logsRes, statsRes] = await Promise.all([
        integrationApi.telegram.getAccounts(),
        integrationApi.telegram.getLogs({ days_back: 7, size: 10 }),
        integrationApi.telegram.getErrorStats(7)
      ]);

      if (accountsRes.ok) {
        const accounts = await accountsRes.json();
        setTelegramAccounts(accounts);
      }

      if (logsRes.ok) {
        const logs = await logsRes.json();
        setTelegramLogs(logs);
      }

      if (statsRes.ok) {
        const stats = await statsRes.json();
        setErrorStats(stats);
      }
    } catch (err) {
      setError('Ошибка загрузки данных интеграций');
      console.error('Error loading integrations data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleConnectPhone = async () => {
    if (!connectForm.phone.trim()) {
      setConnectError('Введите номер телефона');
      return;
    }

    setConnecting(true);
    setConnectError('');

    try {
      const res = await integrationApi.telegram.connectAccount({
        phone: connectForm.phone
      });

      if (res.ok) {
        const data = await res.json();
        if (data.status === 'code_required') {
          setConnectForm(prev => ({ ...prev, step: 'code' }));
        } else if (data.status === '2fa_required') {
          setConnectForm(prev => ({ ...prev, step: 'password' }));
        } else if (data.status === 'success') {
          setConnectForm(prev => ({ ...prev, step: 'success' }));
          loadData(); // Перезагружаем список аккаунтов
        }
      } else {
        const error = await res.json();
        setConnectError(error.detail || 'Ошибка подключения');
      }
    } catch (err) {
      setConnectError('Ошибка сети');
    } finally {
      setConnecting(false);
    }
  };

  const handleConnectCode = async () => {
    if (!connectForm.code.trim()) {
      setConnectError('Введите код подтверждения');
      return;
    }

    setConnecting(true);
    setConnectError('');

    try {
      const res = await integrationApi.telegram.connectAccount({
        phone: connectForm.phone,
        code: connectForm.code
      });

      if (res.ok) {
        const data = await res.json();
        if (data.status === '2fa_required') {
          setConnectForm(prev => ({ ...prev, step: 'password' }));
        } else if (data.status === 'success') {
          setConnectForm(prev => ({ ...prev, step: 'success' }));
          loadData();
        }
      } else {
        const error = await res.json();
        setConnectError(error.detail || 'Неверный код');
      }
    } catch (err) {
      setConnectError('Ошибка сети');
    } finally {
      setConnecting(false);
    }
  };

  const handleConnectPassword = async () => {
    if (!connectForm.password.trim()) {
      setConnectError('Введите пароль 2FA');
      return;
    }

    setConnecting(true);
    setConnectError('');

    try {
      const res = await integrationApi.telegram.connectAccount({
        phone: connectForm.phone,
        code: connectForm.code,
        password: connectForm.password
      });

      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success') {
          setConnectForm(prev => ({ ...prev, step: 'success' }));
          loadData();
        }
      } else {
        const error = await res.json();
        setConnectError(error.detail || 'Неверный пароль');
      }
    } catch (err) {
      setConnectError('Ошибка сети');
    } finally {
      setConnecting(false);
    }
  };

  const handleGenerateQR = async () => {
    try {
      const res = await integrationApi.telegram.generateQR();
      if (res.ok) {
        const data = await res.json();
        setQrCode(data.qr_code);
      }
    } catch (err) {
      console.error('Error generating QR:', err);
    }
  };

  const handleDisconnectAccount = async (sessionId: string) => {
    if (!confirm('Вы уверены, что хотите отключить этот аккаунт?')) return;

    try {
      const res = await integrationApi.telegram.disconnectAccount(sessionId);
      if (res.ok) {
        loadData();
      }
    } catch (err) {
      console.error('Error disconnecting account:', err);
    }
  };

  const resetConnectForm = () => {
    setConnectForm({
      phone: '',
      code: '',
      password: '',
      step: 'phone'
    });
    setConnectError('');
    setQrCode('');
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'text-green-600 bg-green-100';
      case 'error': return 'text-red-600 bg-red-100';
      case 'pending': return 'text-yellow-600 bg-yellow-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  if (loading) {
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
        <Header title="Интеграции" onMenuClick={() => setSidebarOpen(true)} />
        
        <main className="flex-1 p-4 md:p-8">
          {error && <ErrorMessage message={error} />}
          
          {/* Вкладки */}
          <div className="mb-6 border-b border-gray-200 dark:border-gray-700">
            <nav className="flex space-x-8">
              {[
                { key: 'accounts', label: 'Аккаунты Telegram', icon: '👤' },
                { key: 'logs', label: 'Логи операций', icon: '📋' },
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
          {activeTab === 'accounts' && (
            <div className="space-y-6">
              {/* Подключение нового аккаунта */}
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">Подключить Telegram аккаунт</h3>
                
                {connectForm.step === 'phone' && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Номер телефона</label>
                      <input
                        type="tel"
                        placeholder="+7XXXXXXXXXX"
                        value={connectForm.phone}
                        onChange={(e) => setConnectForm(prev => ({ ...prev, phone: e.target.value }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    {connectError && <ErrorMessage message={connectError} />}
                    <div className="flex gap-3">
                      <Button onClick={handleConnectPhone} loading={connecting}>
                        Отправить код
                      </Button>
                      <Button variant="secondary" onClick={handleGenerateQR}>
                        QR-код
                      </Button>
                    </div>
                  </div>
                )}

                {connectForm.step === 'code' && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Код подтверждения</label>
                      <input
                        type="text"
                        placeholder="Введите код из SMS"
                        value={connectForm.code}
                        onChange={(e) => setConnectForm(prev => ({ ...prev, code: e.target.value }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    {connectError && <ErrorMessage message={connectError} />}
                    <div className="flex gap-3">
                      <Button onClick={handleConnectCode} loading={connecting}>
                        Подтвердить
                      </Button>
                      <Button variant="secondary" onClick={resetConnectForm}>
                        Отмена
                      </Button>
                    </div>
                  </div>
                )}

                {connectForm.step === 'password' && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Пароль 2FA</label>
                      <input
                        type="password"
                        placeholder="Введите пароль двухфакторной аутентификации"
                        value={connectForm.password}
                        onChange={(e) => setConnectForm(prev => ({ ...prev, password: e.target.value }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    {connectError && <ErrorMessage message={connectError} />}
                    <div className="flex gap-3">
                      <Button onClick={handleConnectPassword} loading={connecting}>
                        Войти
                      </Button>
                      <Button variant="secondary" onClick={resetConnectForm}>
                        Отмена
                      </Button>
                    </div>
                  </div>
                )}

                {connectForm.step === 'success' && (
                  <div className="space-y-4">
                    <div className="text-green-600 font-medium">✅ Аккаунт успешно подключен!</div>
                    <Button onClick={resetConnectForm}>
                      Подключить еще один
                    </Button>
                  </div>
                )}

                {qrCode && (
                  <div className="mt-4 text-center">
                    <p className="mb-2">Отсканируйте QR-код в Telegram:</p>
                    <img src={`data:image/png;base64,${qrCode}`} alt="QR Code" className="mx-auto" />
                  </div>
                )}
              </div>

              {/* Список подключенных аккаунтов */}
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">Подключенные аккаунты</h3>
                
                {telegramAccounts.length === 0 ? (
                  <p className="text-gray-500">Нет подключенных аккаунтов</p>
                ) : (
                  <div className="space-y-3">
                    {telegramAccounts.map(account => (
                      <div key={account.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${account.is_active ? 'bg-green-500' : 'bg-red-500'}`}></div>
                          <div>
                            <div className="font-medium">{account.phone}</div>
                            <div className="text-sm text-gray-500">
                              Подключен: {formatDate(account.created_at)}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 text-xs rounded-full ${account.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                            {account.is_active ? 'Активен' : 'Неактивен'}
                          </span>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleDisconnectAccount(account.id)}
                          >
                            Отключить
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Логи операций (последние 7 дней)</h3>
              
              {telegramLogs.length === 0 ? (
                <p className="text-gray-500">Нет записей в логах</p>
              ) : (
                <div className="space-y-3">
                  {telegramLogs.map(log => (
                    <div key={log.id} className="p-4 border border-gray-200 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(log.status)}`}>
                            {log.status}
                          </span>
                          <span className="font-medium">{log.action}</span>
                        </div>
                        <span className="text-sm text-gray-500">{formatDate(log.created_at)}</span>
                      </div>
                      {log.error_message && (
                        <div className="text-sm text-red-600 mt-2">
                          Ошибка: {log.error_message}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'stats' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {errorStats && (
                <>
                  <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                    <h4 className="text-sm font-medium text-gray-500 mb-2">Всего операций</h4>
                    <div className="text-2xl font-bold">{errorStats.total_actions}</div>
                  </div>
                  
                  <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                    <h4 className="text-sm font-medium text-gray-500 mb-2">Успешные</h4>
                    <div className="text-2xl font-bold text-green-600">{errorStats.success_count}</div>
                  </div>
                  
                  <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                    <h4 className="text-sm font-medium text-gray-500 mb-2">Ошибки</h4>
                    <div className="text-2xl font-bold text-red-600">{errorStats.error_count}</div>
                  </div>
                  
                  <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                    <h4 className="text-sm font-medium text-gray-500 mb-2">Процент ошибок</h4>
                    <div className="text-2xl font-bold">{errorStats.error_rate}%</div>
                  </div>
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default Integrations; 