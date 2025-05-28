import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const Hero = () => {
  const { t } = useTranslation();
  return (
    <section className="bg-gradient-to-r from-blue-600 to-blue-800 text-white py-20">
      <div className="container mx-auto px-4">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-6 drop-shadow-lg">
            {t('hero_title')}
          </h1>
          <p className="text-xl md:text-2xl mb-8 text-blue-100 drop-shadow">
            {t('hero_subtitle')}
          </p>
          <div className="flex flex-col md:flex-row justify-center gap-4">
            <Link to="/register">
              <button className="bg-white text-blue-700 font-semibold px-8 py-3 rounded-lg shadow-lg hover:bg-blue-100 transition-all duration-200">
                {t('hero_cta')}
              </button>
            </Link>
            <Link to="/login">
              <button className="bg-transparent border border-white text-white font-semibold px-8 py-3 rounded-lg hover:bg-white hover:text-blue-700 transition-all duration-200">
                {t('login')}
              </button>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero; 