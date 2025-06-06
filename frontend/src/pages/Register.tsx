import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useLocation } from 'react-router-dom';

const validateEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

const Register = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: '', password: '', confirm_password: '', agree: false });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (location.state && location.state.error) {
      setError(location.state.error);
    }
  }, [location.state]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!validateEmail(form.email)) {
      setError('Некорректный email');
      return;
    }
    if (form.password.length < 6) {
      setError('Пароль должен быть не менее 6 символов');
      return;
    }
    if (form.password !== form.confirm_password) {
      setError('Пароли не совпадают');
      return;
    }
    if (!form.agree) {
      setError('Необходимо согласиться с условиями');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          confirm_password: form.confirm_password,
          agree: form.agree,
        })
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        setError('Ошибка регистрации: невалидный ответ сервера');
        setLoading(false);
        return;
      }
      if (res.status === 422) {
        setError('Ошибка валидации: ' + (data.detail?.map((d: any) => d.msg).join(', ') || ''));
        setLoading(false);
        return;
      }
      if (res.status === 502) {
        setError('Сервис пользователей временно недоступен. Попробуйте позже.');
        setLoading(false);
        return;
      }
      if (res.status === 400) {
        setError(data.detail || 'Ошибка регистрации');
        setLoading(false);
        return;
      }
      if (res.ok) {
        // После успешной регистрации — автоматический логин
        try {
          // Небольшая задержка перед логином
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          const loginRes = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json',
              'Accept': 'application/json'
            },
            body: JSON.stringify({ 
              email: form.email, 
              password: form.password 
            })
          });

          const loginData = await loginRes.json();
          console.log('Login response:', loginData);
          
          if (!loginRes.ok) {
            setError('Регистрация успешна, но не удалось войти: ' + (loginData.detail || 'Ошибка логина'));
            setLoading(false);
            return;
          }
          
          if (!loginData.access_token && !loginData.refresh_token) {
            console.log('Response structure:', Object.keys(loginData));
            setError('Регистрация успешна, но не получены токены. Попробуйте войти вручную.');
            setLoading(false);
            return;
          }

          localStorage.setItem('access_token', loginData.access_token);
          localStorage.setItem('refresh_token', loginData.refresh_token);
          setForm({ email: '', password: '', confirm_password: '', agree: false });
          navigate('/dashboard');
        } catch (e) {
          console.error('Login error:', e);
          setError('Регистрация успешна, но не удалось войти. Попробуйте войти вручную.');
        } finally {
          setLoading(false);
        }
      } else {
        setError(data.detail || 'Ошибка регистрации');
        setLoading(false);
      }
    } catch (e) {
      setError('Ошибка сети или сервера');
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900 px-4">
      <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md w-full max-w-sm space-y-6">
        <h1 className="text-2xl font-bold text-center mb-2">{t('register')}</h1>
        <div>
          <label htmlFor="email" className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Email</label>
          <input
            type="email"
            id="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            autoComplete="email"
            required
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-900 dark:text-white"
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Пароль</label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              id="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              autoComplete="new-password"
              required
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-900 dark:text-white pr-10"
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600 focus:outline-none"
              aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
            >
              {showPassword ? '🙈' : '👁️'}
            </button>
          </div>
        </div>
        <div>
          <label htmlFor="confirm_password" className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-200">Подтвердите пароль</label>
          <input
            type={showPassword ? 'text' : 'password'}
            id="confirm_password"
            name="confirm_password"
            value={form.confirm_password}
            onChange={handleChange}
            autoComplete="new-password"
            required
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-900 dark:text-white"
          />
        </div>
        <div className="flex items-center">
          <input
            type="checkbox"
            id="agree"
            name="agree"
            checked={form.agree}
            onChange={handleChange}
            className="mr-2"
          />
          <label htmlFor="agree" className="text-sm text-gray-700 dark:text-gray-200">Я соглашаюсь с условиями</label>
        </div>
        {error && <div className="text-red-600 text-center text-sm">{error}</div>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-500 text-white py-3 rounded-lg font-semibold hover:bg-blue-600 transition-all duration-200 disabled:opacity-50"
        >
          {loading ? 'Регистрация...' : 'Зарегистрироваться'}
        </button>
        <div className="text-center text-sm text-gray-500 dark:text-gray-300">
          Уже есть аккаунт?{' '}
          <Link to="/login" className="text-blue-600 hover:underline">Войти</Link>
        </div>
      </form>
    </div>
  );
};

export default Register; 