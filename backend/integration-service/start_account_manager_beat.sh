#!/bin/bash
# Account Manager Beat Scheduler Startup Script

echo "🚀 Starting Account Manager Beat Scheduler..."

# Настройка переменных окружения
export PYTHONPATH="/app:$PYTHONPATH"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Ожидание готовности Redis
echo "⏳ Waiting for Redis..."
until redis-cli -h $REDIS_HOST -p $REDIS_PORT ping | grep -q PONG; do
  echo "Waiting for Redis..."
  sleep 2
done

echo "✅ Redis is ready"

# Запуск Celery Beat для периодических задач Account Manager
echo "📅 Starting Account Manager Celery Beat..."
exec python -m celery -A app.workers.account_manager_workers:celery_app beat \
  --loglevel=$LOG_LEVEL \
  --schedule=/tmp/celerybeat-schedule \
  --pidfile=/tmp/celerybeat.pid