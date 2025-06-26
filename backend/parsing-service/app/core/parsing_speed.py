"""
Parsing speed configuration for different risk/speed levels.

Provides predefined configurations for safe, medium, and fast parsing modes
with appropriate delays and rate limits for Telegram API.
"""

from enum import Enum
from typing import Dict, NamedTuple
from dataclasses import dataclass


class ParsingSpeed(Enum):
    """Parsing speed modes with different risk/speed tradeoffs."""
    SAFE = "safe"       # 🟢 Безопасный (медленный) - минимальный риск FloodWait/ban
    MEDIUM = "medium"   # 🟡 Средний (рекомендуемый) - баланс скорости и безопасности  
    FAST = "fast"       # 🔴 Быстрый (опасный) - высокая скорость, высокий риск


@dataclass
class SpeedConfig:
    """Configuration for a specific parsing speed."""
    # Basic delays (seconds)
    message_delay: float        # Delay between processing messages
    user_request_delay: float   # Delay between user data requests
    api_request_delay: float    # General API request delay
    
    # Rate limits (requests per minute)
    user_requests_per_minute: int   # User data requests limit
    api_requests_per_minute: int    # General API requests limit
    
    # Batch processing
    batch_size: int             # Messages processed in one batch
    batch_delay: float          # Delay between batches
    
    # FloodWait handling  
    max_retries: int           # Max retry attempts
    backoff_multiplier: float  # Exponential backoff multiplier
    
    # User-friendly description
    name: str
    description: str
    estimated_speed: str       # Estimated users per hour
    risk_level: str           # Risk description


# Predefined speed configurations based on research
SPEED_CONFIGS: Dict[ParsingSpeed, SpeedConfig] = {
    
    ParsingSpeed.SAFE: SpeedConfig(
        # Delays
        message_delay=2.0,          # 2 секунды между сообщениями
        user_request_delay=3.0,     # 3 секунды между запросами пользователей
        api_request_delay=1.0,      # 1 секунда между API запросами
        
        # Rate limits  
        user_requests_per_minute=20,    # 20 запросов пользователей в минуту
        api_requests_per_minute=30,     # 30 API запросов в минуту
        
        # Batch processing
        batch_size=10,              # 10 сообщений в батче
        batch_delay=5.0,            # 5 секунд между батчами
        
        # FloodWait handling
        max_retries=5,
        backoff_multiplier=2.0,
        
        # Description
        name="Безопасный",
        description="Минимальный риск FloodWait и блокировок. Медленно, но надежно.",
        estimated_speed="~300-500 пользователей/час",
        risk_level="Очень низкий"
    ),
    
    ParsingSpeed.MEDIUM: SpeedConfig(
        # Delays
        message_delay=0.8,          # 0.8 секунды между сообщениями
        user_request_delay=1.5,     # 1.5 секунды между запросами пользователей
        api_request_delay=0.5,      # 0.5 секунды между API запросами
        
        # Rate limits
        user_requests_per_minute=40,    # 40 запросов пользователей в минуту
        api_requests_per_minute=60,     # 60 API запросов в минуту
        
        # Batch processing
        batch_size=25,              # 25 сообщений в батче
        batch_delay=2.0,            # 2 секунды между батчами
        
        # FloodWait handling
        max_retries=3,
        backoff_multiplier=1.5,
        
        # Description
        name="Средний (рекомендуемый)",
        description="Оптимальный баланс скорости и безопасности. Иногда возможны FloodWait.",
        estimated_speed="~800-1200 пользователей/час",
        risk_level="Средний"
    ),
    
    ParsingSpeed.FAST: SpeedConfig(
        # Delays
        message_delay=0.2,          # 0.2 секунды между сообщениями
        user_request_delay=0.5,     # 0.5 секунды между запросами пользователей
        api_request_delay=0.1,      # 0.1 секунды между API запросами
        
        # Rate limits
        user_requests_per_minute=90,    # 90 запросов пользователей в минуту
        api_requests_per_minute=120,    # 120 API запросов в минуту
        
        # Batch processing
        batch_size=50,              # 50 сообщений в батче
        batch_delay=0.5,            # 0.5 секунды между батчами
        
        # FloodWait handling
        max_retries=2,
        backoff_multiplier=1.2,
        
        # Description
        name="Быстрый (опасный)",
        description="Максимальная скорость. Высокий риск FloodWait и временных блокировок.",
        estimated_speed="~1500-2500 пользователей/час",
        risk_level="Высокий"
    )
}


def get_speed_config(speed: ParsingSpeed) -> SpeedConfig:
    """
    Get configuration for a specific parsing speed.
    
    Args:
        speed: Parsing speed enum value
        
    Returns:
        SpeedConfig object with all timing parameters
    """
    return SPEED_CONFIGS[speed]


def get_available_speeds() -> Dict[str, Dict]:
    """
    Get all available speeds for frontend display.
    
    Returns:
        Dictionary with speed information for UI
    """
    return {
        speed.value: {
            'name': config.name,
            'description': config.description,
            'estimated_speed': config.estimated_speed,
            'risk_level': config.risk_level,
            'user_requests_per_minute': config.user_requests_per_minute,
            'message_delay': config.message_delay
        }
        for speed, config in SPEED_CONFIGS.items()
    }


def parse_speed_from_string(speed_str: str) -> ParsingSpeed:
    """
    Parse parsing speed from string value.
    
    Args:
        speed_str: String representation of speed ("safe", "medium", "fast")
        
    Returns:
        ParsingSpeed enum value, defaults to MEDIUM if invalid
    """
    try:
        return ParsingSpeed(speed_str.lower())
    except ValueError:
        # Default to medium if invalid speed provided
        return ParsingSpeed.MEDIUM


def calculate_estimated_time(user_count: int, speed: ParsingSpeed) -> Dict:
    """
    Calculate estimated parsing time for given user count and speed.
    
    Args:
        user_count: Number of users to parse
        speed: Parsing speed mode
        
    Returns:
        Dictionary with time estimates
    """
    config = get_speed_config(speed)
    
    # Estimate users per hour based on rate limits and delays
    users_per_hour = min(
        config.user_requests_per_minute * 60,  # Based on rate limit
        3600 / config.user_request_delay       # Based on delay
    )
    
    # Account for batch processing efficiency
    if config.batch_size > 1:
        batch_efficiency = 1.2  # 20% efficiency gain from batching
        users_per_hour *= batch_efficiency
    
    # Calculate time estimates
    estimated_hours = user_count / users_per_hour
    estimated_minutes = estimated_hours * 60
    
    return {
        'estimated_hours': round(estimated_hours, 2),
        'estimated_minutes': round(estimated_minutes, 1),
        'users_per_hour': round(users_per_hour),
        'speed_name': config.name,
        'risk_level': config.risk_level
    } 