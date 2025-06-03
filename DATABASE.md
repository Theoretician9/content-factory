# DATABASE.md — Описание баз данных проекта

> **Этот файл содержит подробное описание всех баз данных проекта: структуру таблиц, связи, ограничения, миграции, политики и роли. Здесь фиксируется актуальное состояние схемы каждой базы данных.**

## База данных пользователей (user_service)

### Общая информация
- **Название базы:** user_service
- **Пользователь:** telegraminvi
- **Пароль:** szkTgBhWh6XU
- **Хост:** mysql:3306 (внутри docker-сети)
- **Порт:** 3307 (внешний доступ через SSH-туннель)

### Таблицы

#### users
```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

##### Описание полей:
- `id`: Уникальный идентификатор пользователя
- `username`: Уникальное имя пользователя (не более 50 символов)
- `email`: Уникальный email пользователя
- `hashed_password`: Хешированный пароль (bcrypt)
- `is_active`: Статус активности пользователя
- `created_at`: Дата и время создания записи
- `updated_at`: Дата и время последнего обновления

##### Индексы:
- PRIMARY KEY (`id`)
- UNIQUE INDEX `username_idx` (`username`)
- UNIQUE INDEX `email_idx` (`email`)

##### Ограничения:
- `username` и `email` должны быть уникальными
- `email` должен быть валидным email-адресом
- `hashed_password` не может быть NULL
- `is_active` по умолчанию TRUE

### Миграции
Текущая версия: 1.0

#### Миграция 1.0 (Инициализация)
```sql
-- Создание базы данных
CREATE DATABASE IF NOT EXISTS user_service;
USE user_service;

-- Создание таблицы users
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Создание индексов
CREATE UNIQUE INDEX username_idx ON users(username);
CREATE UNIQUE INDEX email_idx ON users(email);
```

### Политики безопасности
1. Все пароли хешируются с использованием bcrypt перед сохранением
2. Доступ к базе данных только через внутреннюю docker-сеть
3. Внешний доступ только через SSH-туннель
4. Пользователь telegraminvi имеет минимально необходимые права

### Роли и права доступа
```sql
-- Создание пользователя
CREATE USER 'telegraminvi'@'%' IDENTIFIED BY 'szkTgBhWh6XU';

-- Выдача прав
GRANT SELECT, INSERT, UPDATE ON user_service.users TO 'telegraminvi'@'%';
```

### Планы по расширению
1. Добавление таблицы `user_sessions` для хранения сессий
2. Добавление таблицы `user_roles` для поддержки ролей
3. Добавление таблицы `user_permissions` для детального контроля доступа
4. Добавление таблицы `user_activity_log` для аудита действий

### Интеграция с сервисами
- API Gateway обращается к базе через user-service
- user-service использует SQLAlchemy для работы с базой
- Все запросы к базе проходят через connection pool
- Реализовано логирование всех операций с базой

---

## Планируемые базы данных

### База данных биллинга (billing_service)
*Описание будет добавлено после реализации*

### База данных контента (content_service)
*Описание будет добавлено после реализации*

### База данных интеграций (integration_service)
*Описание будет добавлено после реализации*

### База данных воронок (funnel_service)
*Описание будет добавлено после реализации*

### База данных парсинга (parsing_service)
*Описание будет добавлено после реализации*

### База данных рассылок (mailing_service)
*Описание будет добавлено после реализации*

---

> **Этот файл обновляется при любых изменениях в структуре баз данных. Каждое изменение должно быть задокументировано с указанием версии миграции и даты изменения.** 