import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import Button from '../Button';

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
              <Button variant="primary" className="bg-white text-blue-600 hover:bg-blue-50">
                {t('hero_cta')}
              </Button>
            </Link>
            <Link to="/login">
              <Button variant="secondary" className="bg-transparent border-2 border-white hover:bg-white/10">
                {t('login')}
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero; 