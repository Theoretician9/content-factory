import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useUser } from '../UserContext';

const menu = [
  { to: '/dashboard', label: 'Главная', icon: <span>🏠</span> },
  { to: '/integrations', label: 'Интеграции', icon: <span>🔗</span> },
  { to: '/content', label: 'Контент', icon: <span>📝</span> },
  { to: '/autocall', label: 'Автообзвон', icon: <span>📞</span> },
  { to: '/funnels', label: 'Воронки', icon: <span>🔄</span> },
  { to: '/parsing', label: 'Парсинг', icon: <span>🔍</span> },
  { to: '/mailing', label: 'Рассылки/Инвайт', icon: <span>✉️</span> },
  { to: '/create-project', label: 'Создать проект', icon: <span>➕</span> },
  { to: '/analytics', label: 'Аналитика', icon: <span>📊</span> },
];

const Sidebar: React.FC<{ isOpen?: boolean; onClose?: () => void }> = ({ isOpen = true, onClose }) => {
  const location = useLocation();
  const { user } = useUser();
  
  // Добавляем логирование для отладки
  console.log('🔍 Sidebar: user объект:', user);
  console.log('🔍 Sidebar: user?.email:', user?.email);
  console.log('🔍 Sidebar: user?.name:', user?.name);
  return (
    <>
      {/* Overlay для мобильных */}
      {onClose && isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-40 z-30 md:hidden" onClick={onClose}></div>
      )}
      <aside
        className={`
          flex flex-col h-full w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 p-4 justify-between
          fixed md:static z-40 top-0 left-0 transition-transform duration-200
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0 md:relative
        `}
        style={{ minHeight: '100vh' }}
      >
        {/* Крестик для закрытия на мобильных */}
        {onClose && (
          <button
            className="md:hidden absolute top-4 right-4 p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-800 text-2xl text-gray-500"
            onClick={onClose}
            aria-label="Закрыть меню"
          >
            ✕
          </button>
        )}
        <div>
          <div className="flex items-center mb-8">
            <span className="text-2xl font-bold text-blue-600 mr-2">C</span>
            <span className="font-semibold text-lg">Content Factory</span>
          </div>
          <nav className="flex flex-col gap-1">
            {menu.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg font-medium transition-colors duration-150 ${location.pathname === item.to ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'}`}
                onClick={onClose}
              >
                {item.icon}
                {item.label}
              </Link>
            ))}
          </nav>
          
          {/* Блок профиля */}
          <div className="mt-8">
            <div className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-3 px-3">
              Профиль
            </div>
            <div className="flex items-center gap-3 px-3 py-3 rounded-lg bg-gray-50 dark:bg-gray-800">
              <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-lg">
                {user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                  {user?.email || 'Не указан'}
                </div>
                <Link 
                  to="/profile" 
                  className="block text-xs text-blue-500 hover:text-blue-600 hover:underline mt-1" 
                  onClick={onClose}
                >
                  Настройки профиля
                </Link>
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-1 mt-8">
          <Link to="/faq" className="flex items-center gap-2 text-gray-500 hover:text-blue-600 text-sm" onClick={onClose}><span>➕</span> FAQ</Link>
          <Link to="/support" className="flex items-center gap-2 text-gray-500 hover:text-blue-600 text-sm" onClick={onClose}><span>@</span> Поддержка</Link>
          <Link to="/contacts" className="flex items-center gap-2 text-gray-500 hover:text-blue-600 text-sm" onClick={onClose}><span>👤</span> Контакты</Link>
        </div>
      </aside>
    </>
  );
};

export default Sidebar; 