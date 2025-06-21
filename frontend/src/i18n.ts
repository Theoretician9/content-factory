import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  en: {
    translation: {
      // Общие
      welcome: 'Welcome to Content Factory!',
      login: 'Login',
      logout: 'Logout',
      register: 'Register',
      dashboard: 'Dashboard',
      
      // Hero секция
      hero_title: 'Automate Your Content Marketing',
      hero_subtitle: 'Create, manage and optimize your content across all channels',
      hero_cta: 'Get Started',
      
      // Преимущества
      features_title: 'Why Choose Content Factory',
      features_subtitle: 'Powerful features to boost your content marketing',
      feature1_title: 'AI-Powered Content',
      feature1_desc: 'Generate high-quality content using advanced AI',
      feature2_title: 'Multi-Channel',
      feature2_desc: 'Manage content across all your marketing channels',
      feature3_title: 'Analytics',
      feature3_desc: 'Track performance and optimize your content',
      
      // Тарифы
      pricing_title: 'Simple, Transparent Pricing',
      pricing_subtitle: 'Choose the plan that fits your needs',
      pricing_basic: 'Basic',
      pricing_pro: 'Professional',
      pricing_enterprise: 'Enterprise',
      pricing_month: '/month',
      pricing_features: 'Features',
      pricing_cta: 'Get Started',
      popular_plan: 'Most Popular',
      
      // FAQ
      faq_title: 'Frequently Asked Questions',
      faq_subtitle: 'Everything you need to know about Content Factory',
      faq1_q: 'What is Content Factory?',
      faq1_a: 'Content Factory is an AI-powered platform for content marketing automation.',
      faq2_q: 'How does it work?',
      faq2_a: 'Our platform uses AI to generate, optimize and distribute content across channels.',
      faq3_q: 'What channels are supported?',
      faq3_a: 'We support all major social media platforms, blogs, and email marketing.',
      
      // Форма обратной связи
      contact_title: 'Get in Touch',
      contact_subtitle: 'Have questions? We\'re here to help',
      contact_name: 'Name',
      contact_email: 'Email',
      contact_message: 'Message',
      contact_send: 'Send Message',
      contact_success: 'Message sent successfully!',
      contact_error: 'Error sending message. Please try again.',
      
      // Telegram интеграции
      telegram_account: 'Account',
      telegram_bot: 'Bot',
      telegram_public: 'Channel',
      connected_accounts: 'Accounts',
      connected_bots: 'Bots',
      connected_publics: 'Channels',
      connect_telegram_account: 'Connect Telegram Account',
      connect_telegram_bot: 'Connect Bot',
      connect_telegram_public: 'Connect Channel',
      bot_token: 'Bot Token',
      bot_name: 'Bot Name (optional)',
      public_username: 'Channel Username',
      public_name: 'Channel Name (optional)',
      bot_token_placeholder: 'Paste bot token from @BotFather',
      public_username_placeholder: '@channelname or channel ID',
      connect_button: 'Connect',
    },
  },
  ru: {
    translation: {
      // Общие
      welcome: 'Добро пожаловать в Content Factory!',
      login: 'Войти',
      logout: 'Выход',
      register: 'Регистрация',
      dashboard: 'Кабинет',
      
      // Hero секция
      hero_title: 'Автоматизируйте Ваш Контент-Маркетинг',
      hero_subtitle: 'Создавайте, управляйте и оптимизируйте контент во всех каналах',
      hero_cta: 'Начать',
      
      // Преимущества
      features_title: 'Почему Content Factory',
      features_subtitle: 'Мощные инструменты для развития контент-маркетинга',
      feature1_title: 'ИИ-Контент',
      feature1_desc: 'Создавайте качественный контент с помощью ИИ',
      feature2_title: 'Мультиканальность',
      feature2_desc: 'Управляйте контентом во всех маркетинговых каналах',
      feature3_title: 'Аналитика',
      feature3_desc: 'Отслеживайте эффективность и оптимизируйте контент',
      
      // Тарифы
      pricing_title: 'Простая и Прозрачная Ценовая Политика',
      pricing_subtitle: 'Выберите план, который подходит вам',
      pricing_basic: 'Базовый',
      pricing_pro: 'Профессиональный',
      pricing_enterprise: 'Корпоративный',
      pricing_month: '/месяц',
      pricing_features: 'Возможности',
      pricing_cta: 'Начать',
      popular_plan: 'Самый популярный',
      
      // FAQ
      faq_title: 'Часто Задаваемые Вопросы',
      faq_subtitle: 'Всё, что нужно знать о Content Factory',
      faq1_q: 'Что такое Content Factory?',
      faq1_a: 'Content Factory - это платформа для автоматизации контент-маркетинга на базе ИИ.',
      faq2_q: 'Как это работает?',
      faq2_a: 'Наша платформа использует ИИ для создания, оптимизации и распространения контента.',
      faq3_q: 'Какие каналы поддерживаются?',
      faq3_a: 'Мы поддерживаем все основные социальные сети, блоги и email-маркетинг.',
      
      // Форма обратной связи
      contact_title: 'Свяжитесь с Нами',
      contact_subtitle: 'Есть вопросы? Мы готовы помочь',
      contact_name: 'Имя',
      contact_email: 'Email',
      contact_message: 'Сообщение',
      contact_send: 'Отправить',
      contact_success: 'Сообщение успешно отправлено!',
      contact_error: 'Ошибка отправки. Попробуйте еще раз.',
      
      // Telegram интеграции
      telegram_account: 'Аккаунт',
      telegram_bot: 'Бот',
      telegram_public: 'Паблик',
      connected_accounts: 'Аккаунты',
      connected_bots: 'Боты',
      connected_publics: 'Паблики',
      connect_telegram_account: 'Подключить Telegram аккаунт',
      connect_telegram_bot: 'Подключить бота',
      connect_telegram_public: 'Подключить паблик',
      bot_token: 'Токен бота',
      bot_name: 'Название бота (опционально)',
      public_username: 'Username паблика',
      public_name: 'Название паблика (опционально)',
      bot_token_placeholder: 'Вставьте токен от @BotFather',
      public_username_placeholder: '@channelname или ID паблика',
      connect_button: 'Подключить',
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