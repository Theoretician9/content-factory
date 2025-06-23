"""
Prometheus metrics for multi-platform parsing service.
"""

import logging
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server, CollectorRegistry, REGISTRY

from .config import settings, Platform, TaskStatus

logger = logging.getLogger(__name__)

# Use a custom registry to avoid conflicts
metrics_registry = CollectorRegistry()

# =============================================================================
# TASK METRICS
# =============================================================================

# Task counters by platform and status
try:
    tasks_total = Counter(
        'parsing_tasks_total',
        'Total number of parsing tasks',
        ['platform', 'task_type', 'status', 'user_id'],
        registry=metrics_registry
    )
except ValueError:
    # Metric already exists, get it from registry
    tasks_total = None

try:
    tasks_created = Counter(
        'parsing_tasks_created_total',
        'Total number of created parsing tasks',
        ['platform', 'task_type'],
        registry=metrics_registry
    )
except ValueError:
    tasks_created = None

try:
    tasks_completed = Counter(
        'parsing_tasks_completed_total',
        'Total number of completed parsing tasks',
        ['platform', 'task_type'],
        registry=metrics_registry
    )
except ValueError:
    tasks_completed = None

try:
    tasks_failed = Counter(
        'parsing_tasks_failed_total',
        'Total number of failed parsing tasks',
        ['platform', 'task_type', 'error_type'],
        registry=metrics_registry
    )
except ValueError:
    tasks_failed = None

# Task duration metrics
try:
    task_duration = Histogram(
        'parsing_task_duration_seconds',
        'Time spent processing parsing tasks',
        ['platform', 'task_type'],
        buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600, 7200],  # 1s to 2h
        registry=metrics_registry
    )
except ValueError:
    task_duration = None

# Currently running tasks
try:
    active_tasks = Gauge(
        'parsing_active_tasks',
        'Number of currently active parsing tasks',
        ['platform', 'task_type'],
        registry=metrics_registry
    )
except ValueError:
    active_tasks = None

# =============================================================================
# PARSING RESULTS METRICS
# =============================================================================

# Results counters
results_parsed = Counter(
    'parsing_results_total',
    'Total number of parsed items',
    ['platform', 'source_type', 'content_type']
)

# Results with media
results_with_media = Counter(
    'parsing_results_with_media_total',
    'Total number of parsed items with media',
    ['platform', 'media_type']
)

# Parsing rate (items per second)
parsing_rate = Histogram(
    'parsing_rate_items_per_second',
    'Parsing rate in items per second',
    ['platform'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 20, 50, 100]
)

# =============================================================================
# PLATFORM ACCOUNT METRICS
# =============================================================================

# Account usage
accounts_used = Counter(
    'parsing_accounts_used_total',
    'Total number of times accounts were used',
    ['platform', 'account_status']
)

# Rate limits hit
rate_limits_hit = Counter(
    'parsing_rate_limits_total',
    'Total number of rate limits hit',
    ['platform', 'limit_type']
)

# Account errors
account_errors = Counter(
    'parsing_account_errors_total',
    'Total number of account errors',
    ['platform', 'error_type']
)

# Available accounts gauge
available_accounts = Gauge(
    'parsing_available_accounts',
    'Number of available accounts per platform',
    ['platform']
)

# =============================================================================
# PLATFORM-SPECIFIC METRICS
# =============================================================================

# Telegram specific
telegram_flood_waits = Counter(
    'telegram_flood_waits_total',
    'Total number of Telegram FloodWait errors',
    ['wait_seconds_bucket']
)

telegram_channels_parsed = Counter(
    'telegram_channels_parsed_total',
    'Total number of Telegram channels/groups parsed',
    ['channel_type']  # channel, group, supergroup
)

# Instagram specific (Phase 2)
instagram_posts_parsed = Counter(
    'instagram_posts_parsed_total',
    'Total number of Instagram posts parsed',
    ['post_type']  # post, story, reel
)

# WhatsApp specific (Phase 3)
whatsapp_messages_parsed = Counter(
    'whatsapp_messages_parsed_total',
    'Total number of WhatsApp messages parsed',
    ['chat_type']  # group, individual
)

# =============================================================================
# SYSTEM METRICS
# =============================================================================

# Service info
service_info = Info(
    'parsing_service_info',
    'Information about the parsing service'
)

# Database connections
database_connections = Gauge(
    'parsing_database_connections',
    'Number of active database connections'
)

# Vault connections
vault_operations = Counter(
    'parsing_vault_operations_total',
    'Total number of Vault operations',
    ['operation_type', 'status']  # get_secret, authenticate, etc.
)

# Celery workers
celery_workers = Gauge(
    'parsing_celery_workers',
    'Number of active Celery workers',
    ['queue', 'status']
)

# =============================================================================
# METRICS HELPER FUNCTIONS
# =============================================================================

class MetricsCollector:
    """Helper class for collecting metrics."""
    
    def __init__(self):
        self.service_info.info({
            'version': settings.VERSION,
            'app_name': settings.APP_NAME,
            'supported_platforms': ','.join([p.value for p in settings.SUPPORTED_PLATFORMS])
        })
    
    # Task metrics
    def record_task_created(self, platform: Platform, task_type: str):
        """Record task creation."""
        tasks_created.labels(platform=platform.value, task_type=task_type).inc()
        active_tasks.labels(platform=platform.value, task_type=task_type).inc()
    
    def record_task_completed(self, platform: Platform, task_type: str, duration: float):
        """Record task completion."""
        tasks_completed.labels(platform=platform.value, task_type=task_type).inc()
        task_duration.labels(platform=platform.value, task_type=task_type).observe(duration)
        active_tasks.labels(platform=platform.value, task_type=task_type).dec()
    
    def record_task_failed(self, platform: Platform, task_type: str, error_type: str):
        """Record task failure."""
        tasks_failed.labels(
            platform=platform.value, 
            task_type=task_type, 
            error_type=error_type
        ).inc()
        active_tasks.labels(platform=platform.value, task_type=task_type).dec()
    
    # Results metrics
    def record_results_parsed(
        self, 
        platform: Platform, 
        source_type: str, 
        content_type: str, 
        count: int = 1
    ):
        """Record parsed results."""
        results_parsed.labels(
            platform=platform.value,
            source_type=source_type,
            content_type=content_type
        ).inc(count)
    
    def record_media_parsed(self, platform: Platform, media_type: str, count: int = 1):
        """Record parsed media."""
        results_with_media.labels(
            platform=platform.value,
            media_type=media_type
        ).inc(count)
    
    def record_parsing_rate(self, platform: Platform, rate: float):
        """Record parsing rate."""
        parsing_rate.labels(platform=platform.value).observe(rate)
    
    # Account metrics
    def record_account_used(self, platform: Platform, account_status: str):
        """Record account usage."""
        accounts_used.labels(
            platform=platform.value,
            account_status=account_status
        ).inc()
    
    def record_rate_limit(self, platform: Platform, limit_type: str):
        """Record rate limit hit."""
        rate_limits_hit.labels(
            platform=platform.value,
            limit_type=limit_type
        ).inc()
    
    def record_account_error(self, platform: Platform, error_type: str):
        """Record account error."""
        account_errors.labels(
            platform=platform.value,
            error_type=error_type
        ).inc()
    
    def update_available_accounts(self, platform: Platform, count: int):
        """Update available accounts count."""
        available_accounts.labels(platform=platform.value).set(count)
    
    # Platform-specific metrics
    def record_telegram_flood_wait(self, wait_seconds: int):
        """Record Telegram FloodWait."""
        # Bucket wait times for better aggregation
        if wait_seconds <= 60:
            bucket = "0-60s"
        elif wait_seconds <= 300:
            bucket = "60-300s"
        elif wait_seconds <= 3600:
            bucket = "300-3600s"
        else:
            bucket = "3600s+"
        
        telegram_flood_waits.labels(wait_seconds_bucket=bucket).inc()
    
    def record_telegram_channel_parsed(self, channel_type: str):
        """Record Telegram channel parsed."""
        telegram_channels_parsed.labels(channel_type=channel_type).inc()
    
    # System metrics
    def update_database_connections(self, count: int):
        """Update database connections count."""
        database_connections.set(count)
    
    def record_vault_operation(self, operation_type: str, status: str):
        """Record Vault operation."""
        vault_operations.labels(
            operation_type=operation_type,
            status=status
        ).inc()
    
    def update_celery_workers(self, queue: str, status: str, count: int):
        """Update Celery workers count."""
        celery_workers.labels(queue=queue, status=status).set(count)


# Global metrics collector
metrics = MetricsCollector()


def start_metrics_server():
    """Start Prometheus metrics server."""
    if settings.PROMETHEUS_METRICS_ENABLED:
        try:
            start_http_server(settings.METRICS_PORT)
            logger.info(f"📊 Prometheus metrics server started on port {settings.METRICS_PORT}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start metrics server: {e}")
            return False
    else:
        logger.info("📊 Prometheus metrics disabled")
        return False


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return metrics 