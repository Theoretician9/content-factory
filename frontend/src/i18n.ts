import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  en: {
    translation: {
      welcome: 'Welcome to Content Factory!',
      login: 'Login',
      register: 'Register',
      dashboard: 'Dashboard',
    },
  },
  ru: {
    translation: {
      welcome: 'Добро пожаловать в Content Factory!',
      login: 'Войти',
      register: 'Регистрация',
      dashboard: 'Кабинет',
    },
  },
};

i18n.use(initReactI18next).init({
  resources,
  lng: 'ru',
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
});

export default i18n; 