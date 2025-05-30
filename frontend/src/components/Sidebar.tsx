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

const Sidebar: React.FC = () => {
  const location = useLocation();
  const { user } = useUser();
  return (
    <aside className="flex flex-col h-full w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 p-4 justify-between">
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
            >
              {item.icon}
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-8 flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800">
          <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-lg">
            {user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          <div>
            <div className="font-semibold">{user?.name || user?.email || 'Профиль'}</div>
            <Link to="/profile" className="text-xs text-blue-500 hover:underline">Настройки профиля</Link>
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-1 mt-8">
        <Link to="/faq" className="flex items-center gap-2 text-gray-500 hover:text-blue-600 text-sm"><span>➕</span> FAQ</Link>
        <Link to="/support" className="flex items-center gap-2 text-gray-500 hover:text-blue-600 text-sm"><span>@</span> Поддержка</Link>
        <Link to="/contacts" className="flex items-center gap-2 text-gray-500 hover:text-blue-600 text-sm"><span>👤</span> Контакты</Link>
      </div>
    </aside>
  );
};

export default Sidebar; 