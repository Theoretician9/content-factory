import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const Pricing = () => {
  const { t } = useTranslation();

  const plans = [
    {
      name: t('pricing_basic'),
      price: '0 ₽' + t('pricing_month'),
      features: [
        t('feature1_title'),
        t('feature2_title'),
        t('feature3_title'),
      ],
      buttonText: t('pricing_cta'),
      popular: false,
    },
    {
      name: t('pricing_pro'),
      price: '990 ₽' + t('pricing_month'),
      features: [
        t('feature1_title'),
        t('feature2_title'),
        t('feature3_title'),
      ],
      buttonText: t('pricing_cta'),
      popular: true,
    },
    {
      name: t('pricing_enterprise'),
      price: t('pricing_month'),
      features: [
        t('feature1_title'),
        t('feature2_title'),
        t('feature3_title'),
      ],
      buttonText: t('pricing_cta'),
      popular: false,
    },
  ];

  return (
    <section className="py-12 md:py-20 bg-gray-900 dark:bg-black">
      <div className="container mx-auto px-4">
        <div className="text-center mb-10 md:mb-16">
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-4 text-white drop-shadow-lg">
            {t('pricing_title')}
          </h2>
          <p className="text-base sm:text-lg md:text-xl text-gray-300">
            {t('pricing_subtitle')}
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-8">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`relative bg-white dark:bg-gray-800 p-5 md:p-8 rounded-lg shadow-lg hover:shadow-2xl transition-shadow duration-300 border border-gray-100 dark:border-gray-700 hover:-translate-y-1 transform cursor-pointer ${plan.popular ? 'ring-2 ring-blue-500 scale-105 z-10' : ''}`}
            >
              {plan.popular && (
                <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-xs font-bold px-4 py-1 rounded-full shadow-lg">
                  {t('popular_plan')}
                </div>
              )}
              <h3 className="text-lg md:text-2xl font-bold mb-4 text-gray-900 dark:text-white">{plan.name}</h3>
              <div className="text-2xl md:text-4xl font-bold mb-6 text-blue-700 dark:text-blue-400">{plan.price}</div>
              <ul className="mb-8">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="mb-2 flex items-center">
                    <svg
                      className="w-5 h-5 text-green-500 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    <span className="text-gray-700 dark:text-gray-200 text-sm md:text-base">{feature}</span>
                  </li>
                ))}
              </ul>
              <Link
                to="/register"
                className={`block text-center py-3 px-6 rounded-lg font-semibold transition-all duration-200 w-full md:w-auto ${
                  plan.popular
                    ? 'bg-blue-500 text-white hover:bg-blue-600 shadow-lg'
                    : 'bg-gray-100 text-gray-800 hover:bg-gray-200 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600'
                }`}
              >
                {plan.buttonText}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Pricing; 