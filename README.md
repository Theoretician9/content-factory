<<<<<<< HEAD
# Content Factory - Автоматическая синхронизация

## Настройка автоматической синхронизации

### 1. Установка необходимых программ

1. Установите Git для Windows:
   - Скачайте с https://git-scm.com/download/win
   - Установите, используя все настройки по умолчанию
   - При установке выберите опцию "Git Bash Here"

2. Установите Webdock CLI:
   - Откройте PowerShell от имени администратора
   - Выполните: `winget install webdock-cli`
   - Или: `choco install webdock-cli`

### 2. Настройка GitHub

1. Откройте PowerShell от имени администратора
2. Выполните команды:
   ```powershell
   git config --global user.name "Ваше имя"
   git config --global user.email "ваш.email@example.com"
   ```
3. Создайте SSH ключ:
   ```powershell
   ssh-keygen -t ed25519 -C "ваш.email@example.com"
   ```
4. Скопируйте содержимое файла `C:\Users\ваше_имя\.ssh\id_ed25519.pub`
5. Перейдите на GitHub -> Settings -> SSH and GPG keys -> New SSH key
6. Вставьте скопированный ключ и сохраните

### 3. Настройка сервера

1. Откройте Git Bash (правый клик в папке -> Git Bash Here)
2. Создайте SSH ключ для сервера:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/server_key -C "server-key"
   ```
3. Скопируйте публичный ключ:
   ```bash
   cat ~/.ssh/server_key.pub
   ```
4. Подключитесь к серверу:
   ```bash
   ssh root@92.113.146.148
   ```
5. На сервере выполните:
   ```bash
   mkdir -p ~/.ssh
   echo "ВСТАВЬТЕ_СЮДА_ВАШ_ПУБЛИЧНЫЙ_КЛЮЧ" >> ~/.ssh/authorized_keys
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/authorized_keys
   ```

### 4. Настройка автоматической синхронизации

1. Создайте задачу в Планировщике задач Windows:
   - Откройте "Планировщик задач"
   - Создайте новую задачу
   - Триггер: каждые 5 минут
   - Действие: Запустить программу
   - Программа: `powershell.exe`
   - Аргументы: `-ExecutionPolicy Bypass -File "C:\Users\nikit\cod\content-factory\sync-to-github.ps1"`
   - Повторите для `sync-to-server.ps1`

### 5. Проверка работы

1. Создайте тестовый файл в папке `C:\Users\nikit\cod\content-factory`
2. Подождите 5 минут
3. Проверьте, что файл появился:
   - В вашем GitHub репозитории
   - На сервере по адресу http://92.113.146.148

## Устранение неполадок

Если что-то не работает:

1. Проверьте логи в Планировщике задач
2. Убедитесь, что Git Bash установлен
3. Проверьте подключение к интернету
4. Проверьте SSH подключение:
   ```bash
   ssh -i ~/.ssh/server_key root@92.113.146.148
   ```

## Важные замечания

- Храните SSH ключи в безопасном месте
- Регулярно делайте резервные копии
- Не удаляйте файлы `.git` в папке проекта
- Проверяйте права доступа к файлам на сервере 
=======
# content-factory
Контент завод
>>>>>>> eee548d5810721a1868bc390018eb18a474fb962
