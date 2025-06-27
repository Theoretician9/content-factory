import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 768);
  
  // Платформы состояние
  const [selectedPlatform, setSelectedPlatform] = useState<'telegram' | 'instagram' | 'whatsapp' | 'youtube' | 'tiktok' | 'threads'>('telegram');
  
  // Telegram табы состояние
  const [telegramConnectTab, setTelegramConnectTab] = useState<'account' | 'bot' | 'public'>('account');
  const [telegramListTab, setTelegramListTab] = useState<'accounts' | 'bots' | 'publics'>('accounts');
  
  // Telegram состояние
  const [telegramAccounts, setTelegramAccounts] = useState<TelegramAccount[]>([]);
  const [telegramBots, setTelegramBots] = useState<any[]>([]);
  const [telegramPublics, setTelegramPublics] = useState<any[]>([]);
  const [telegramLogs, setTelegramLogs] = useState<IntegrationLog[]>([]);
  const [errorStats, setErrorStats] = useState<ErrorStats | null>(null);
  const [activeTab, setActiveTab] = useState<'platforms' | 'logs' | 'stats'>('platforms');
  
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
  
  // ✅ QR код состояния и polling
  const [qrStatus, setQrStatus] = useState<'idle' | 'generating' | 'waiting' | '2fa_required' | 'success' | 'expired' | 'error'>('idle');
  const [qrPolling, setQrPolling] = useState(false);
  const [qrError, setQrError] = useState('');
  const [qrPassword, setQrPassword] = useState('');
  
  // ✅ Ref для отслеживания текущего статуса polling
  const qrPollingRef = useRef(false);
  const qrStatusRef = useRef<'idle' | 'generating' | 'waiting' | 'success' | 'expired' | 'error'>('idle');
  
  // Подключение бота
  const [botForm, setBotForm] = useState({
    token: '',
    name: ''
  });
  const [connectingBot, setConnectingBot] = useState(false);
  const [botError, setBotError] = useState('');
  
  // Подключение паблика
  const [publicForm, setPublicForm] = useState({
    username: '',
    name: ''
  });
  const [connectingPublic, setConnectingPublic] = useState(false);
  const [publicError, setPublicError] = useState('');

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

  // ✅ ФУНКЦИЯ ПРОВЕРКИ QR АВТОРИЗАЦИИ
  const checkQRAuthorization = async (password?: string) => {
    try {
      const res = await integrationApi.telegram.checkQRAuthorization(password);
      if (res.ok) {
        const data = await res.json();
        console.log('🔍 QR check response:', data);
        
        if (data.status === 'success') {
          qrStatusRef.current = 'success';
          qrPollingRef.current = false;
          setQrStatus('success');
          setQrPolling(false);
          setConnectForm(prev => ({ ...prev, step: 'success' }));
          loadData(); // Перезагружаем список аккаунтов
          return true;
        } else if (data.status === '2fa_required') {
          qrStatusRef.current = '2fa_required';
          qrPollingRef.current = false;
          setQrStatus('2fa_required');
          setQrPolling(false);
          setQrError(''); // Очищаем ошибки
          console.log('🔐 QR 2FA required, showing password field');
          return false;
        } else if (data.status === 'qr_expired') {
          qrStatusRef.current = 'expired';
          qrPollingRef.current = false;
          setQrStatus('expired');
          setQrPolling(false);
          setQrError('QR код истек. Сгенерируйте новый');
          return false;
        } else if (data.status === 'qr_waiting') {
          // Продолжаем ожидание, без изменений
          return false;
        } else if (data.status === 'error') {
          qrStatusRef.current = 'error';
          qrPollingRef.current = false;
          setQrStatus('error');
          setQrPolling(false);
          setQrError(data.message || 'Ошибка QR авторизации');
          return false;
        }
      } else {
        console.error('QR check API error:', res.status);
        return false;
      }
    } catch (err) {
      console.error('Error checking QR authorization:', err);
      return false;
    }
    return false;
  };

  // ✅ ФУНКЦИЯ POLLING QR СТАТУСА С ИСПРАВЛЕННОЙ ЛОГИКОЙ
  const startQRPolling = () => {
    if (qrPollingRef.current) return; // Предотвращаем множественный polling
    
    qrPollingRef.current = true;
    qrStatusRef.current = 'waiting';
    setQrPolling(true);
    setQrStatus('waiting');
    
    const pollInterval = setInterval(async () => {
      if (!qrPollingRef.current) {
        clearInterval(pollInterval);
        return;
      }
      
      console.log('🔄 Polling QR status...');
      const success = await checkQRAuthorization();
      
      if (success || qrStatusRef.current === 'expired' || qrStatusRef.current === 'error') {
        clearInterval(pollInterval);
        qrPollingRef.current = false;
        setQrPolling(false);
      }
    }, 3000); // Проверяем каждые 3 секунды
    
    // Автоматическая остановка через 5 минут (QR код живет 5 минут)
    setTimeout(() => {
      if (qrPollingRef.current && qrStatusRef.current === 'waiting') {
        clearInterval(pollInterval);
        qrPollingRef.current = false;
        setQrPolling(false);
        setQrStatus('expired');
        setQrError('QR код истек. Сгенерируйте новый');
      }
    }, 300000); // 5 минут
  };

  const handleGenerateQR = async () => {
    setQrStatus('generating');
    setQrError('');
    setConnectError('');
    
    try {
      console.log('🔑 Generating QR code...');
      const res = await integrationApi.telegram.generateQR();
      if (res.ok) {
        const data = await res.json();
        setQrCode(data.qr_code);
        console.log('✅ QR code generated, starting polling...');
        
        // ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Запускаем polling сразу после генерации
        startQRPolling();
      } else {
        setQrStatus('error');
        setQrError('Ошибка генерации QR кода');
      }
    } catch (err) {
      console.error('Error generating QR:', err);
      setQrStatus('error');
      setQrError('Ошибка сети при генерации QR кода');
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
    // ✅ Сброс QR состояний и ref
    qrStatusRef.current = 'idle';
    qrPollingRef.current = false;
    setQrStatus('idle');
    setQrPolling(false);
    setQrError('');
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
                { key: 'platforms', label: 'Платформы', icon: '🔗' },
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
          {activeTab === 'platforms' && (
            <div className="space-y-6">
              {/* Выбор платформы */}
              <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 backdrop-blur-sm">
                <h3 className="text-xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 dark:from-white dark:to-gray-300 bg-clip-text text-transparent mb-6">Подключить платформу</h3>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                  {[
                    { 
                      key: 'telegram', 
                      name: 'Telegram', 
                      icon: (
                        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                          <path d="m20.665 3.717-17.73 6.837c-1.21.486-1.203 1.161-.222 1.462l4.552 1.42 10.532-6.645c.498-.303.953-.14.579.192l-8.533 7.701h-.002l.002.001-.314 4.692c.46 0 .663-.211.921-.46l2.211-2.15 4.599 3.397c.848.467 1.457.227 1.668-.791l3.018-14.228c.309-1.239-.473-1.8-1.281-1.436z"/>
                        </svg>
                      ), 
                      bgColor: 'bg-blue-500', 
                      available: true 
                    },
                    { 
                      key: 'instagram', 
                      name: 'Instagram', 
                      icon: (
                        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                          <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                        </svg>
                      ), 
                      bgColor: 'bg-gradient-to-r from-purple-500 to-pink-500', 
                      available: false 
                    },
                    { 
                      key: 'whatsapp', 
                      name: 'WhatsApp', 
                      icon: (
                        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893A11.821 11.821 0 0020.893 3.488"/>
                        </svg>
                      ), 
                      bgColor: 'bg-green-500', 
                      available: false 
                    },
                    { 
                      key: 'youtube', 
                      name: 'YouTube', 
                      icon: (
                        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                          <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                        </svg>
                      ), 
                      bgColor: 'bg-red-500', 
                      available: false 
                    },
                    { 
                      key: 'tiktok', 
                      name: 'TikTok', 
                      icon: (
                        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                          <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
                        </svg>
                      ), 
                      bgColor: 'bg-black', 
                      available: false 
                    },
                    { 
                      key: 'threads', 
                      name: 'Threads', 
                      icon: (
                        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                          <path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.181 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.589 12c.027 3.086.718 5.496 2.057 7.164 1.43 1.781 3.631 2.695 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.284 3.272-.886 1.102-2.14 1.704-3.73 1.79-1.202.065-2.361-.218-3.259-.801-1.063-.689-1.685-1.74-1.752-2.964-.065-1.19.408-2.285 1.33-3.082.88-.76 2.119-1.207 3.583-1.291a13.853 13.853 0 0 1 3.02.142c-.126-.742-.375-1.332-.74-1.774-.513-.624-1.267-.935-2.237-.926-1.518.014-2.653.75-3.35 2.17-.699 1.425-.876 3.206-.526 5.304l-1.969.434c-.44-2.642-.198-4.755.718-6.46 1.022-1.904 2.693-2.918 4.963-3.014 1.423-.067 2.583.403 3.44 1.396.83.96 1.283 2.264 1.342 3.876l.005.078c.04.661.04 1.331.04 2.004v.896c1.055.485 1.853 1.21 2.368 2.152 1.007 1.844.956 4.342-.142 6.578-1.362 2.201-3.615 3.387-6.704 3.527-.244.011-.487.017-.728.017l.007.004zm-2.701-7.508c-1.006.267-1.636.665-1.872 1.182-.216.473-.147.985.206 1.533.424.659 1.2 1.065 2.068 1.081 1.237-.073 2.137-.534 2.68-1.37.485-.743.647-1.741.485-2.97-.157-.078-.316-.15-.477-.213a11.69 11.69 0 0 0-3.09-.243z"/>
                        </svg>
                      ), 
                      bgColor: 'bg-gray-800', 
                      available: false 
                    }
                  ].map(platform => (
                    <button
                      key={platform.key}
                      onClick={() => platform.available && setSelectedPlatform(platform.key as any)}
                      className={`
                        relative flex flex-col items-center p-4 rounded-lg border-2 transition-all duration-200
                        ${selectedPlatform === platform.key 
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' 
                          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                        }
                        ${!platform.available ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-md'}
                      `}
                      disabled={!platform.available}
                    >
                      <div className={`w-12 h-12 rounded-full ${platform.bgColor} flex items-center justify-center text-white text-xl mb-2`}>
                        {platform.icon}
                      </div>
                      <span className="text-sm font-medium text-center">{platform.name}</span>
                      {!platform.available && (
                        <div className="absolute -top-1 -right-1 bg-yellow-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                          Soon
                        </div>
                      )}
                      {selectedPlatform === platform.key && (
                        <div className="absolute -top-1 -right-1 bg-blue-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                          ✓
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>

                            {/* Контент выбранной платформы */}
              {selectedPlatform === 'telegram' && (
                <>
                  {/* Подключение элементов Telegram */}
                <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 backdrop-blur-sm">
                  {/* Табы для типа подключения */}
                  <div className="mb-8">
                    <nav className="flex gap-2 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl">
                      {[
                        { key: 'account', label: t('connect_telegram_account'), icon: '👤', color: 'from-blue-500 to-cyan-500' },
                        { key: 'bot', label: t('connect_telegram_bot'), icon: '🤖', color: 'from-purple-500 to-pink-500' },
                        { key: 'public', label: t('connect_telegram_public'), icon: '📢', color: 'from-orange-500 to-red-500' }
                      ].map(tab => (
                        <button
                          key={tab.key}
                          onClick={() => setTelegramConnectTab(tab.key as any)}
                          className={`
                            relative flex items-center gap-3 px-6 py-3 rounded-lg font-medium text-sm transition-all duration-300 ease-out
                            ${telegramConnectTab === tab.key
                              ? `bg-gradient-to-r ${tab.color} text-white shadow-lg shadow-${tab.color.split('-')[1]}-500/25 transform scale-105`
                              : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-white dark:hover:bg-gray-700 hover:shadow-md'
                            }
                          `}
                        >
                          <span className={`text-lg transition-transform duration-300 ${
                            telegramConnectTab === tab.key ? 'scale-110' : ''
                          }`}>
                            {tab.icon}
                          </span>
                          <span className="whitespace-nowrap">{tab.label}</span>
                          {telegramConnectTab === tab.key && (
                            <div className="absolute inset-0 bg-gradient-to-r from-white/20 to-transparent rounded-lg pointer-events-none" />
                          )}
                        </button>
                      ))}
                    </nav>
                  </div>

                  {/* Контент табов подключения */}
                  {telegramConnectTab === 'account' && (
                    <div>
                      <h3 className="text-lg font-semibold mb-4">{t('connect_telegram_account')}</h3>
                
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
                      <Button 
                        variant="secondary" 
                        onClick={handleGenerateQR}
                        loading={qrStatus === 'generating'}
                        disabled={qrStatus === 'waiting' || qrStatus === 'generating'}
                      >
                        {qrStatus === 'generating' ? 'Генерация...' : 
                         qrStatus === 'waiting' ? 'QR активен' : 'QR-код'}
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

                {/* ✅ УЛУЧШЕННАЯ СЕКЦИЯ QR КОДА С СОСТОЯНИЯМИ */}
                {(qrCode || qrStatus !== 'idle') && (
                  <div className="mt-6 p-6 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-2xl border border-blue-200 dark:border-blue-800">
                    <div className="text-center space-y-4">
                      {/* Заголовок с иконкой */}
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
                          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 16h4.01M20 12h.01m-5.03-.71l1.06 1.06m-1.06-1.06l1.06-1.06m-1.06 1.06L16 12.01M12 8h.01M12 16h.01m.01-4h-.01m0 0h.01"/>
                          </svg>
                        </div>
                        <h4 className="text-lg font-semibold text-blue-900 dark:text-blue-100">
                          QR-код авторизация
                        </h4>
                      </div>

                      {/* Статус и QR код */}
                      {qrStatus === 'generating' && (
                        <div className="space-y-3">
                          <div className="flex items-center justify-center gap-2">
                            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
                            <span className="text-blue-700 dark:text-blue-300">Генерация QR кода...</span>
                          </div>
                        </div>
                      )}

                      {qrStatus === 'waiting' && qrCode && (
                        <div className="space-y-4">
                          <div className="flex items-center justify-center gap-2">
                            <div className="animate-pulse w-3 h-3 bg-orange-500 rounded-full"></div>
                            <span className="text-orange-700 dark:text-orange-300 font-medium">
                              Ожидание сканирования...
                            </span>
                          </div>
                          
                          <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-lg inline-block">
                            <img 
                              src={`data:image/png;base64,${qrCode}`} 
                              alt="QR Code" 
                              className="mx-auto w-48 h-48"
                            />
                          </div>
                          
                          <div className="text-sm text-gray-600 dark:text-gray-400 max-w-md mx-auto">
                            <p className="mb-2">📱 <strong>Откройте Telegram</strong> на телефоне</p>
                            <p className="mb-2">⚙️ Перейдите в <strong>Настройки → Устройства</strong></p>
                            <p>📷 Нажмите <strong>"Подключить устройство"</strong> и отсканируйте QR код</p>
                          </div>
                          
                          {qrPolling && (
                            <div className="text-xs text-blue-600 dark:text-blue-400">
                              🔄 Автоматическая проверка каждые 3 секунды...
                            </div>
                          )}
                        </div>
                      )}

                      {qrStatus === 'success' && (
                        <div className="space-y-3">
                          <div className="flex items-center justify-center gap-2">
                            <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                              </svg>
                            </div>
                            <span className="text-green-700 dark:text-green-300 font-semibold">
                              ✅ Аккаунт успешно подключен!
                            </span>
                          </div>
                          <Button onClick={resetConnectForm} variant="secondary" size="sm">
                            Подключить еще один
                          </Button>
                        </div>
                      )}

                      {qrStatus === 'expired' && (
                        <div className="space-y-3">
                          <div className="flex items-center justify-center gap-2">
                            <div className="w-6 h-6 bg-yellow-500 rounded-full flex items-center justify-center">
                              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                              </svg>
                            </div>
                            <span className="text-yellow-700 dark:text-yellow-300 font-medium">
                              ⏰ QR код истек
                            </span>
                          </div>
                          {qrError && (
                            <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-2 rounded">
                              {qrError}
                            </div>
                          )}
                          <Button onClick={handleGenerateQR} variant="secondary" size="sm">
                            Создать новый QR код
                          </Button>
                        </div>
                      )}

                      {qrStatus === 'error' && (
                        <div className="space-y-3">
                          <div className="flex items-center justify-center gap-2">
                            <div className="w-6 h-6 bg-red-500 rounded-full flex items-center justify-center">
                              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
                              </svg>
                            </div>
                            <span className="text-red-700 dark:text-red-300 font-medium">
                              ❌ Ошибка QR авторизации
                            </span>
                          </div>
                          {qrError && (
                            <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-3 rounded-lg">
                              {qrError}
                            </div>
                          )}
                          <div className="flex gap-2 justify-center">
                            <Button onClick={handleGenerateQR} variant="secondary" size="sm">
                              Попробовать снова
                            </Button>
                            <Button onClick={resetConnectForm} variant="secondary" size="sm">
                              Отмена
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                    </div>
                  )}

                  {/* Форма подключения бота */}
                  {telegramConnectTab === 'bot' && (
                    <div>
                      <h3 className="text-lg font-semibold mb-4">{t('connect_telegram_bot')}</h3>
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium mb-2">{t('bot_token')}</label>
                          <input
                            type="text"
                            placeholder={t('bot_token_placeholder')}
                            value={botForm.token}
                            onChange={(e) => setBotForm(prev => ({ ...prev, token: e.target.value }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-2">{t('bot_name')}</label>
                          <input
                            type="text"
                            placeholder="Мой бот"
                            value={botForm.name}
                            onChange={(e) => setBotForm(prev => ({ ...prev, name: e.target.value }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        {botError && <ErrorMessage message={botError} />}
                        <Button onClick={() => console.log('Connect bot')} loading={connectingBot}>
                          {t('connect_button')}
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Форма подключения паблика */}
                  {telegramConnectTab === 'public' && (
                    <div>
                      <h3 className="text-lg font-semibold mb-4">{t('connect_telegram_public')}</h3>
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium mb-2">{t('public_username')}</label>
                          <input
                            type="text"
                            placeholder={t('public_username_placeholder')}
                            value={publicForm.username}
                            onChange={(e) => setPublicForm(prev => ({ ...prev, username: e.target.value }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-2">{t('public_name')}</label>
                          <input
                            type="text"
                            placeholder="Мой паблик"
                            value={publicForm.name}
                            onChange={(e) => setPublicForm(prev => ({ ...prev, name: e.target.value }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        {publicError && <ErrorMessage message={publicError} />}
                        <Button onClick={() => console.log('Connect public')} loading={connectingPublic}>
                          {t('connect_button')}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Подключенные элементы */}
                <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8 backdrop-blur-sm">
                  {/* Табы для списков */}
                  <div className="mb-8">
                    <nav className="flex gap-3 p-2 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-700 rounded-2xl border border-gray-200 dark:border-gray-600">
                      {[
                        { key: 'accounts', label: t('connected_accounts'), icon: '👤', count: telegramAccounts.length, gradient: 'from-emerald-500 to-teal-600' },
                        { key: 'bots', label: t('connected_bots'), icon: '🤖', count: telegramBots.length, gradient: 'from-violet-500 to-purple-600' },
                        { key: 'publics', label: t('connected_publics'), icon: '📢', count: telegramPublics.length, gradient: 'from-rose-500 to-pink-600' }
                      ].map(tab => (
                        <button
                          key={tab.key}
                          onClick={() => setTelegramListTab(tab.key as any)}
                          className={`
                            group relative flex items-center gap-3 px-5 py-3 rounded-xl font-semibold text-sm 
                            transition-all duration-500 ease-out transform
                            ${telegramListTab === tab.key
                              ? `bg-gradient-to-br ${tab.gradient} text-white shadow-xl shadow-${tab.gradient.split('-')[1]}-500/30 scale-105 -translate-y-0.5`
                              : 'text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-white dark:hover:bg-gray-600 hover:shadow-lg hover:scale-102 hover:-translate-y-0.5'
                            }
                          `}
                        >
                          <div className={`
                            flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-300
                            ${telegramListTab === tab.key
                              ? 'bg-white/20 backdrop-blur-sm'
                              : 'bg-gray-200 dark:bg-gray-700 group-hover:bg-gray-300 dark:group-hover:bg-gray-600'
                            }
                          `}>
                            <span className={`text-lg transition-all duration-300 ${
                              telegramListTab === tab.key ? 'scale-110 filter drop-shadow-sm' : 'group-hover:scale-110'
                            }`}>
                              {tab.icon}
                            </span>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <span className="whitespace-nowrap">{tab.label}</span>
                            {tab.count > 0 && (
                              <div className={`
                                relative flex items-center justify-center min-w-[20px] h-5 px-2 rounded-full text-xs font-bold
                                transition-all duration-300 transform
                                ${telegramListTab === tab.key
                                  ? 'bg-white/25 text-white backdrop-blur-sm scale-110'
                                  : 'bg-gradient-to-r from-blue-500 to-blue-600 text-white group-hover:scale-110'
                                }
                              `}>
                                <span className="relative z-10">{tab.count}</span>
                                {telegramListTab === tab.key && (
                                  <div className="absolute inset-0 bg-white/10 rounded-full animate-pulse" />
                                )}
                              </div>
                            )}
                          </div>
                          
                          {/* Активный индикатор */}
                          {telegramListTab === tab.key && (
                            <div className="absolute inset-0 rounded-xl overflow-hidden">
                              <div className="absolute inset-0 bg-gradient-to-r from-white/10 via-transparent to-white/5" />
                              <div className="absolute top-0 left-1/4 w-1/2 h-px bg-white/30" />
                              <div className="absolute bottom-0 right-1/4 w-1/2 h-px bg-white/20" />
                            </div>
                          )}
                        </button>
                      ))}
                    </nav>
                  </div>

                  {/* Список аккаунтов */}
                  {telegramListTab === 'accounts' && (
                    <div>
                      <h3 className="text-lg font-semibold mb-4">{t('connected_accounts')}</h3>
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
                  )}

                  {/* Список ботов */}
                  {telegramListTab === 'bots' && (
                    <div>
                      <h3 className="text-lg font-semibold mb-4">{t('connected_bots')}</h3>
                      {telegramBots.length === 0 ? (
                        <p className="text-gray-500">Нет подключенных ботов</p>
                      ) : (
                        <div className="space-y-3">
                          {telegramBots.map((bot, index) => (
                            <div key={index} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                              <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                                <div>
                                  <div className="font-medium">{bot.name || 'Бот без названия'}</div>
                                  <div className="text-sm text-gray-500">@{bot.username}</div>
                                </div>
                              </div>
                              <Button variant="secondary" size="sm">
                                Отключить
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Список пабликов */}
                  {telegramListTab === 'publics' && (
                    <div>
                      <h3 className="text-lg font-semibold mb-4">{t('connected_publics')}</h3>
                      {telegramPublics.length === 0 ? (
                        <p className="text-gray-500">Нет подключенных пабликов</p>
                      ) : (
                        <div className="space-y-3">
                          {telegramPublics.map((pub, index) => (
                            <div key={index} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                              <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                                <div>
                                  <div className="font-medium">{pub.name || 'Паблик без названия'}</div>
                                  <div className="text-sm text-gray-500">@{pub.username}</div>
                                </div>
                              </div>
                              <Button variant="secondary" size="sm">
                                Отключить
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                </>
              )}

              {/* Заглушки для других платформ */}
              {selectedPlatform !== 'telegram' && (
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                  <h3 className="text-lg font-semibold mb-4">
                    {selectedPlatform === 'instagram' && 'Instagram интеграция'}
                    {selectedPlatform === 'whatsapp' && 'WhatsApp интеграция'} 
                    {selectedPlatform === 'youtube' && 'YouTube интеграция'}
                    {selectedPlatform === 'tiktok' && 'TikTok интеграция'}
                    {selectedPlatform === 'threads' && 'Threads интеграция'}
                  </h3>
                  <div className="text-center py-12">
                    <div className="text-6xl mb-4">🚧</div>
                    <h4 className="text-xl font-semibold mb-2">Скоро будет доступно</h4>
                    <p className="text-gray-500">
                      Интеграция с {selectedPlatform} находится в разработке. 
                      Мы добавим эту функцию в ближайшее время.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">
                Логи операций {selectedPlatform === 'telegram' ? 'Telegram' : selectedPlatform} (последние 7 дней)
              </h3>
              
              {selectedPlatform === 'telegram' ? (
                telegramLogs.length === 0 ? (
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
                )
              ) : (
                <div className="text-center py-12">
                  <div className="text-4xl mb-4">📊</div>
                  <p className="text-gray-500">
                    Логи для {selectedPlatform} будут доступны после подключения
                  </p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'stats' && (
            selectedPlatform === 'telegram' ? (
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
            ) : (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="text-center py-12">
                  <div className="text-4xl mb-4">📈</div>
                  <h4 className="text-xl font-semibold mb-2">Статистика {selectedPlatform}</h4>
                  <p className="text-gray-500">
                    Статистика будет доступна после подключения и активности на платформе
                  </p>
                </div>
              </div>
            )
          )}
        </main>
      </div>
    </div>
  );
};

export default Integrations; 