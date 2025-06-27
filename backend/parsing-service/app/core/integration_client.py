"""
Integration Service client for getting user accounts and credentials.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional

from .config import settings, Platform
from .auth import decode_jwt_token

logger = logging.getLogger(__name__)


class IntegrationServiceClient:
    """Client for Integration Service API."""
    
    def __init__(self):
        self.base_url = settings.INTEGRATION_SERVICE_URL
        self.timeout = 30.0
        
    async def get_user_accounts(
        self, 
        user_id: int, 
        platform: Platform,
        jwt_token: str
    ) -> List[Dict[str, Any]]:
        """
        Get user's accounts for specific platform.
        
        Args:
            user_id: User ID
            platform: Platform (telegram, instagram, whatsapp)
            jwt_token: JWT token for authentication
            
        Returns:
            List of user accounts with credentials
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/telegram/accounts",
                    headers={
                        "Authorization": f"Bearer {jwt_token}",
                        "Content-Type": "application/json"
                    },
                    params={
                        "active_only": True
                    }
                )
                
                if response.status_code == 200:
                    accounts = response.json()
                    # Преобразуем формат данных из Integration Service
                    formatted_accounts = []
                    for acc in accounts:
                        formatted_accounts.append({
                            "account_id": str(acc.get("id")),
                            "user_id": acc.get("user_id"),
                            "phone": acc.get("phone"),
                            "is_active": acc.get("is_active"),
                            "session_metadata": acc.get("session_metadata", {}),
                            "status": "active" if acc.get("is_active") else "inactive"
                        })
                    logger.info(f"✅ Found {len(formatted_accounts)} {platform.value} accounts for user {user_id}")
                    return formatted_accounts
                else:
                    logger.error(f"❌ Failed to get accounts: {response.status_code} - {response.text}")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ Error getting user accounts: {e}")
            return []
    
    async def get_account_credentials(
        self,
        user_id: int,
        account_id: str,
        platform: Platform,
        jwt_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get credentials for specific account from Telegram session data.
        
        Args:
            user_id: User ID
            account_id: Account identifier (UUID)
            platform: Platform
            jwt_token: JWT token for authentication
            
        Returns:
            Account credentials or None
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Get specific account details
                response = await client.get(
                    f"{self.base_url}/api/v1/telegram/accounts/{account_id}",
                    headers={
                        "Authorization": f"Bearer {jwt_token}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    account_data = response.json()
                    
                    # Extract session_data from session_metadata
                    session_metadata = account_data.get("session_metadata", {})
                    session_data = session_metadata.get("session_data")
                    
                    if session_data:
                        credentials = {
                            "session_data": session_data,
                            "phone": account_data.get("phone"),
                            "account_id": account_id
                        }
                        logger.info(f"✅ Retrieved credentials for account {account_id}")
                        return credentials
                    else:
                        logger.warning(f"⚠️ No session_data found for account {account_id}")
                        return None
                else:
                    logger.error(f"❌ Failed to get account details: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error getting account credentials: {e}")
            return None
    
    async def update_account_status(
        self,
        account_id: str,
        status: str,
        error_message: Optional[str] = None,
        jwt_token: str = None
    ) -> bool:
        """
        Update account status (active, error, rate_limited, etc.).
        
        Args:
            account_id: Account identifier
            status: New status
            error_message: Error message if status is error
            jwt_token: JWT token for authentication
            
        Returns:
            True if update successful
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                data = {"status": status}
                if error_message:
                    data["error_message"] = error_message
                
                response = await client.patch(
                    f"{self.base_url}/v1/accounts/{account_id}/status",
                    headers={
                        "Authorization": f"Bearer {jwt_token}",
                        "Content-Type": "application/json"
                    },
                    json=data
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Updated account {account_id} status to {status}")
                    return True
                else:
                    logger.error(f"❌ Failed to update account status: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error updating account status: {e}")
            return False
    
    async def get_available_account(
        self,
        user_id: int,
        platform: Platform,
        jwt_token: str,
        exclude_accounts: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get next available account for parsing.
        
        Args:
            user_id: User ID
            platform: Platform
            jwt_token: JWT token
            exclude_accounts: List of account IDs to exclude
            
        Returns:
            Available account with credentials or None
        """
        try:
            accounts = await self.get_user_accounts(user_id, platform, jwt_token)
            
            if exclude_accounts is None:
                exclude_accounts = []
            
            # Filter available accounts
            available_accounts = [
                acc for acc in accounts 
                if acc.get("account_id") not in exclude_accounts 
                and acc.get("status") == "active"
                and not acc.get("rate_limited", False)
            ]
            
            if not available_accounts:
                logger.warning(f"⚠️ No available {platform.value} accounts for user {user_id}")
                return None
            
            # Get the first available account
            account = available_accounts[0]
            account_id = account["account_id"]
            
            # Get credentials
            credentials = await self.get_account_credentials(
                user_id, account_id, platform, jwt_token
            )
            
            if credentials:
                account["credentials"] = credentials
                logger.info(f"✅ Selected account {account_id} for parsing")
                return account
            else:
                logger.error(f"❌ Failed to get credentials for account {account_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting available account: {e}")
            return None
    
    async def log_parsing_activity(
        self,
        user_id: int,
        account_id: str,
        platform: Platform,
        activity_type: str,
        details: Dict[str, Any],
        jwt_token: str
    ) -> bool:
        """
        Log parsing activity for account monitoring.
        
        Args:
            user_id: User ID
            account_id: Account identifier
            platform: Platform
            activity_type: Type of activity (parse_start, parse_complete, rate_limit, error)
            details: Activity details
            jwt_token: JWT token
            
        Returns:
            True if logged successfully
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                data = {
                    "account_id": account_id,
                    "platform": platform.value,
                    "activity_type": activity_type,
                    "details": details
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/accounts/activity",
                    headers={
                        "Authorization": f"Bearer {jwt_token}",
                        "Content-Type": "application/json"
                    },
                    json=data
                )
                
                if response.status_code == 201:
                    logger.debug(f"📝 Logged activity {activity_type} for account {account_id}")
                    return True
                else:
                    logger.warning(f"⚠️ Failed to log activity: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error logging activity: {e}")
            return False
    
    async def health_check(self) -> bool:
        """
        Check Integration Service health.
        
        Returns:
            True if service is healthy
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
                
                if response.status_code == 200:
                    logger.info("✅ Integration Service is healthy")
                    return True
                else:
                    logger.error(f"❌ Integration Service unhealthy: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Integration Service health check failed: {e}")
            return False


# Global client instance
_integration_client: Optional[IntegrationServiceClient] = None


def get_integration_client() -> IntegrationServiceClient:
    """Get global Integration Service client instance."""
    global _integration_client
    if _integration_client is None:
        _integration_client = IntegrationServiceClient()
    return _integration_client 