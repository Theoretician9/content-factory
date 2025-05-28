import React from 'react';
import { useTranslation } from 'react-i18next';

const Landing = () => {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-3xl font-bold mb-4">{t('welcome')}</h1>
      <div className="space-x-4">
        <a href="/login" className="btn btn-primary">{t('login')}</a>
        <a href="/register" className="btn btn-secondary">{t('register')}</a>
      </div>
    </div>
  );
};

export default Landing; 