import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface FormData {
  name: string;
  email: string;
  message: string;
}

const validateEmail = (email: string) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};

const ContactForm = () => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<FormData>({
    name: '',
    email: '',
    message: '',
  });
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error' | 'invalid'>('idle');

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateEmail(formData.email)) {
      setStatus('invalid');
      return;
    }
    setStatus('loading');
    try {
      // TODO: Implement actual form submission
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setStatus('success');
      setFormData({ name: '', email: '', message: '' });
    } catch (error) {
      setStatus('error');
    }
  };

  return (
    <section className="py-20 bg-gray-900 dark:bg-black">
      <div className="container max-w-screen-xl mx-auto px-2">
        <div className="max-w-2xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white drop-shadow-lg">
              {t('contact_title')}
            </h2>
            <p className="text-xl text-gray-300">
              {t('contact_subtitle')}
            </p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-6 bg-white dark:bg-gray-800 p-8 rounded-lg shadow-lg">
            <div>
              <label
                htmlFor="name"
                className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1"
              >
                {t('contact_name')}
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1"
              >
                {t('contact_email')}
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label
                htmlFor="message"
                className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1"
              >
                {t('contact_message')}
              </label>
              <textarea
                id="message"
                name="message"
                value={formData.message}
                onChange={handleChange}
                required
                rows={4}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <button
              type="submit"
              disabled={status === 'loading'}
              className="w-full bg-blue-500 text-white py-3 px-6 rounded-lg font-semibold hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 transition-all duration-200"
            >
              {status === 'loading' ? t('contact_send') + '...' : t('contact_send')}
            </button>
            {status === 'success' && (
              <p className="text-green-600 dark:text-green-400 text-center font-semibold animate-pulse">
                {t('contact_success')}
              </p>
            )}
            {status === 'error' && (
              <p className="text-red-600 dark:text-red-400 text-center font-semibold">
                {t('contact_error')}
              </p>
            )}
            {status === 'invalid' && (
              <p className="text-yellow-600 dark:text-yellow-400 text-center font-semibold">
                Некорректный email
              </p>
            )}
          </form>
        </div>
      </div>
    </section>
  );
};

export default ContactForm; 