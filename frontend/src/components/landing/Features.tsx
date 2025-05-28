import React from 'react';
import { useTranslation } from 'react-i18next';

const Features = () => {
  const { t } = useTranslation();

  const features = [
    {
      title: t('feature1_title'),
      description: t('feature1_desc'),
      icon: '🤖',
    },
    {
      title: t('feature2_title'),
      description: t('feature2_desc'),
      icon: '📱',
    },
    {
      title: t('feature3_title'),
      description: t('feature3_desc'),
      icon: '📊',
    },
  ];

  return (
    <section className="py-20 bg-gray-50 dark:bg-gray-900">
      <div className="container max-w-screen-xl mx-auto px-2">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4 text-blue-800 dark:text-white drop-shadow-lg">
            {t('features_title')}
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300">
            {t('features_subtitle')}
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 overflow-x-auto">
          {features.map((feature, index) => (
            <div
              key={index}
              className="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg hover:shadow-2xl transition-shadow duration-300 border border-gray-100 dark:border-gray-700 hover:-translate-y-1 transform cursor-pointer"
            >
              <div className="text-5xl mb-4 drop-shadow-lg">{feature.icon}</div>
              <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-white">{feature.title}</h3>
              <p className="text-gray-600 dark:text-gray-300">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Features; 