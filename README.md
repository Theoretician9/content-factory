# Content Factory

Content Factory - это микросервисная платформа для автоматизации создания и управления контентом с интеграцией различных социальных сетей и мессенджеров.

## 🚀 Возможности

- Автоматизация создания и публикации контента
- Интеграция с популярными социальными сетями и мессенджерами
- Управление пользователями и правами доступа
- Система биллинга и подписок
- Мониторинг и аналитика
- Вебхуки для интеграции с внешними системами

## 🏗 Архитектура

Проект построен на микросервисной архитектуре с использованием следующих компонентов:

### Основные сервисы
- **API Gateway** - Единая точка входа для всех клиентских запросов
- **User Service** - Управление пользователями и аутентификация
- **Billing Service** - Обработка платежей и управление подписками
- **Scenario Service** - Управление сценариями автоматизации
- **Content Service** - Управление контентом
- **Invite Service** - Управление приглашениями
- **Parsing Service** - Парсинг и обработка данных
- **Integration Service** - Интеграция с внешними сервисами
- **Task Worker** - Фоновые задачи и обработка очередей

### Инфраструктура
- **RabbitMQ** - Очереди сообщений
- **Redis** - Кэширование и хранение сессий
- **MySQL** - Основное хранилище данных
- **Elasticsearch** - Поиск и аналитика
- **Kibana** - Визуализация данных
- **Prometheus** - Мониторинг
- **Grafana** - Дашборды и метрики
- **Alertmanager** - Управление алертами

## 🛠 Технологии

- **Backend**: Python 3.11
- **Message Broker**: RabbitMQ 3.12
- **Cache**: Redis 7.0
- **Database**: MySQL 8.0
- **Search**: Elasticsearch 7.17
- **Monitoring**: Prometheus, Grafana
- **Containerization**: Docker, Docker Compose

## 🚀 Быстрый старт

### Предварительные требования

- Docker
- Docker Compose
- Git

### Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/your-username/content-factory.git
cd content-factory
```

2. Создайте файл .env:
```bash
cp .env.example .env
```

3. Настройте переменные окружения в .env файле

4. Запустите сервисы:
```bash
docker-compose up -d
```

### Проверка работоспособности

1. API Gateway: http://localhost:8000/health
2. Kibana: http://localhost:5601
3. Grafana: http://localhost:3000
4. Prometheus: http://localhost:9090
5. RabbitMQ Management: http://localhost:15672

## 📚 Документация

- [API Documentation](docs/api.md)
- [Architecture Overview](docs/architecture.md)
- [Development Guide](docs/development.md)
- [Deployment Guide](docs/deployment.md)
- [Monitoring Guide](docs/monitoring.md)

## 🔧 Разработка

### Структура проекта

```
content-factory/
├── backend/
│   ├── api-gateway/
│   ├── user-service/
│   ├── billing-service/
│   ├── scenario-service/
│   ├── content-service/
│   ├── invite-service/
│   ├── parsing-service/
│   ├── integration-service/
│   └── task-worker/
├── frontend/
├── docs/
├── docker/
├── prometheus/
├── grafana/
├── alertmanager/
└── docker-compose.yml
```

### Локальная разработка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите сервисы в режиме разработки:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

## 📊 Мониторинг

- Prometheus метрики доступны на порту 9090
- Grafana дашборды на порту 3000
- Alertmanager на порту 9093
- Kibana на порту 5601

## 🔐 Безопасность

- Все пароли и секреты хранятся в .env файле
- Используется HTTPS для всех внешних соединений
- Реализована система ролей и разрешений
- Регулярное обновление зависимостей
- Мониторинг безопасности

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функциональности
3. Внесите изменения
4. Создайте Pull Request

## 📝 Лицензия

MIT License - см. [LICENSE](LICENSE) файл для деталей

## 👥 Команда

- Project Lead: [Your Name]
- Backend Team: [Team Members]
- Frontend Team: [Team Members]
- DevOps: [Team Members]

## 📞 Поддержка

- Email: support@content-factory.com
- Issues: GitHub Issues
- Documentation: [docs/](docs/)
