# Frontend для Integration Service

## Обзор

Фронтенд для управления интеграциями с внешними сервисами, в первую очередь с Telegram API. Реализован как часть основного React приложения Content Factory.

## Функциональность

### 🔗 Страница интеграций (/integrations)

**Три основные вкладки:**

1. **Аккаунты Telegram** 👤
   - Подключение новых Telegram аккаунтов
   - Пошаговый процесс: телефон → код → пароль 2FA (если нужен)
   - Альтернативный вход через QR-код
   - Список подключенных аккаунтов с статусом
   - Отключение аккаунтов

2. **Логи операций** 📋
   - История всех операций за последние 7 дней
   - Статусы: success, error, pending
   - Детали ошибок
   - Фильтрация по типам операций

3. **Статистика** 📊
   - Общее количество операций
   - Успешные и неуспешные операции
   - Процент ошибок
   - Метрики за последние 7 дней

## Архитектура

### Компоненты

- **`pages/Integrations.tsx`** - основная страница с вкладками
- **Используемые общие компоненты:**
  - `Sidebar.tsx` - навигация (пункт "Интеграции" уже добавлен)
  - `Header.tsx` - шапка страницы  
  - `Button.tsx` - кнопки с поддержкой loading состояния
  - `Loader.tsx` - индикатор загрузки
  - `ErrorMessage.tsx` - отображение ошибок

### API интеграция

**Файл: `api.ts`**

```typescript
// Основная функция для Dashboard
api.getIntegrationsStatus() // Возвращает статус для карточки на главной

// Детальное API для страницы интеграций
integrationApi.telegram.getAccounts()
integrationApi.telegram.connectAccount()
integrationApi.telegram.getLogs()
integrationApi.telegram.getErrorStats()
// ... и другие функции
```

### Маршрутизация

```typescript
// App.tsx
<Route path="/integrations" element={
  <PrivateRoute>
    <Integrations />
  </PrivateRoute>
} />
```

## API Gateway конфигурация

**Маршруты фронтенда проксируются:**
- `/api/integrations/*` → `integration-service:8000/api/v1/*`
- `/api/v1/integrations/*` → `integration-service:8000/` (совместимость)

## Интерфейс пользователя

### Дизайн
- **Адаптивный дизайн** - работает на desktop и mobile
- **Темная тема** - поддержка dark mode
- **TailwindCSS** - консистентный стиль с остальным приложением
- **Иконки** - эмодзи для простоты и читаемости

### UX особенности
- **Пошаговый процесс** подключения аккаунтов
- **Real-time статусы** подключенных аккаунтов
- **Подтверждение действий** (отключение аккаунта)
- **Loading состояния** для всех операций
- **Обработка ошибок** с понятными сообщениями

## Типы данных

```typescript
interface TelegramAccount {
  id: string;
  phone: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface IntegrationLog {
  id: string;
  integration_type: string;
  action: string;
  status: 'success' | 'error' | 'pending';
  error_message?: string;
  created_at: string;
}

interface ErrorStats {
  total_actions: number;
  error_count: number;
  success_count: number;
  error_rate: number;
  period_days: number;
}
```

## Безопасность

- **JWT токены** - все запросы проходят авторизацию
- **CORS настроен** в API Gateway
- **Валидация данных** на фронтенде и бэкенде
- **Rate limiting** в API Gateway

## Развертывание

1. **Сборка фронтенда:**
   ```bash
   cd frontend
   npm run build
   ```

2. **Статика автоматически копируется** в `./frontend-static/`

3. **Nginx отдает** собранные файлы на `https://content-factory.xyz`

## Статус реализации

✅ **Готово:**
- Полный UI для управления Telegram аккаунтами
- API интеграция с Integration Service
- Роутинг и навигация
- Адаптивный дизайн
- Обработка ошибок и loading состояний

⏳ **Требует конфигурации:**
- Валидные Telegram API ключи в Integration Service
- Тестирование на реальных данных

🔄 **Планы развития:**
- Интеграции с другими платформами (WhatsApp, Instagram)
- Расширенная аналитика и графики
- Групповые операции с аккаунтами
- Планировщик задач для интеграций

## Техническая архитектура

```
Frontend (React/TypeScript)
    ↓ /api/integrations/*
API Gateway (nginx)  
    ↓ proxy_pass
Integration Service (FastAPI)
    ↓
PostgreSQL Database
```

Все компоненты работают в Docker и готовы для продакшена. 