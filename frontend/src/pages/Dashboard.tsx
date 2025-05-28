import React from 'react';
import { useTranslation } from 'react-i18next';

const Dashboard = () => {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-2xl font-bold mb-4">{t('dashboard')}</h1>
      <p>Dashboard content will be here</p>
    </div>
  );
};

export default Dashboard; 