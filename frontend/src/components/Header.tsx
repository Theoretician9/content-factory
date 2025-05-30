import React from 'react';
import { useTranslation } from 'react-i18next';
import { useUser } from '../UserContext';

const Header: React.FC<{ title?: string; onMenuClick?: () => void }> = ({ title = 'Главная', onMenuClick }) => {
  const { t, i18n } = useTranslation();
  const { logout } = useUser();

  const handleLangChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    i18n.changeLanguage(e.target.value);
  };

  return (
    <header className="flex items-center justify-between px-4 md:px-8 py-4 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
      <div className="flex items-center gap-3">
        {/* Гамбургер только на мобильных */}
        {onMenuClick && (
          <button
            className="md:hidden p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-800 focus:outline-none"
            onClick={onMenuClick}
            aria-label="Открыть меню"
          >
            <span className="block w-6 h-0.5 bg-gray-700 dark:bg-gray-200 mb-1"></span>
            <span className="block w-6 h-0.5 bg-gray-700 dark:bg-gray-200 mb-1"></span>
            <span className="block w-6 h-0.5 bg-gray-700 dark:bg-gray-200"></span>
          </button>
        )}
        <h1 className="text-xl font-bold">{title}</h1>
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={logout}
          className="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 px-4 py-2 rounded-lg font-semibold hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900 transition-all duration-200"
        >
          {t('logout') || 'Выход'}
        </button>
        <select
          value={i18n.language}
          onChange={handleLangChange}
          className="bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700"
        >
          <option value="ru">RU</option>
          <option value="en">EN</option>
        </select>
      </div>
    </header>
  );
};

export default Header; 