import React from 'react';
import { useTranslation } from 'react-i18next';
import { useUser } from '../UserContext';

const Dashboard = () => {
  const { t } = useTranslation();
  const { user, loading, error, logout } = useUser();

  if (loading) {
    return <div className="flex flex-col items-center justify-center min-h-screen text-lg">Загрузка...</div>;
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-2xl font-bold mb-4">{t('dashboard')}</h1>
      {user && (
        <div className="mb-4 text-lg">Добро пожаловать, {user.name || user.email}!</div>
      )}
      <p>Dashboard content will be here</p>
      <button
        onClick={logout}
        className="mt-8 bg-red-500 text-white px-6 py-2 rounded-lg font-semibold hover:bg-red-600 transition-all duration-200"
      >
        Выйти
      </button>
      {error && <div className="mt-4 text-blue-600 text-center">{error}</div>}
    </div>
  );
};

export default Dashboard; 