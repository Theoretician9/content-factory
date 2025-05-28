import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const Hero = () => {
  const { t } = useTranslation();

  return (
    <section className="bg-gradient-to-r from-blue-600 to-blue-800 text-white py-20">
      <div className="container mx-auto px-4">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-6">
            {t('hero_title')}
          </h1>
          <p className="text-xl md:text-2xl mb-8 text-blue-100">
            {t('hero_subtitle')}
          </p>
          <div className="space-x-4">
            <Link to="/register">
              <button className="bg-white text-blue-600 px-4 py-2 rounded font-semibold">{t('hero_cta')}</button>
            </Link>
            <Link to="/login">
              <button className="bg-transparent border-2 border-white px-4 py-2 rounded font-semibold text-white">{t('login')}</button>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero; 