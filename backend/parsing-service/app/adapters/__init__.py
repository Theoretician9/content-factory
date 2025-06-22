"""
Platform adapters for multi-platform parsing.

This module contains adapters for different social media platforms:
- TelegramAdapter: Telegram groups/channels parsing
- InstagramAdapter: Instagram posts/accounts parsing (planned)
- WhatsAppAdapter: WhatsApp groups parsing (planned)
"""

from .base import BasePlatformAdapter
from .telegram import TelegramAdapter

# Import future adapters when implemented
# from .instagram import InstagramAdapter
# from .whatsapp import WhatsAppAdapter

__all__ = [
    "BasePlatformAdapter",
    "TelegramAdapter"
    # "InstagramAdapter",  # Phase 2
    # "WhatsAppAdapter"    # Phase 3
] 