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
    <section className="py-20">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            {t('pricing_title')}
          </h2>
          <p className="text-xl text-gray-600">
            {t('pricing_subtitle')}
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`bg-white p-8 rounded-lg shadow-lg ${
                plan.popular ? 'border-2 border-blue-500' : ''
              }`}
            >
              {plan.popular && (
                <div className="bg-blue-500 text-white text-center py-1 rounded-t-lg -mt-8 -mx-8 mb-4">
                  {t('popular_plan')}
                </div>
              )}
              <h3 className="text-2xl font-bold mb-4">{plan.name}</h3>
              <div className="text-4xl font-bold mb-6">{plan.price}</div>
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
                    {feature}
                  </li>
                ))}
              </ul>
              <Link
                to="/register"
                className={`block text-center py-3 px-6 rounded-lg font-semibold ${
                  plan.popular
                    ? 'bg-blue-500 text-white hover:bg-blue-600'
                    : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
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