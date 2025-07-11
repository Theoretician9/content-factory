"""
Account Manager for managing Telegram accounts used in parsing.

This module provides centralized account management including:
- Account state tracking
- Task assignment to available accounts  
- FloodWait handling at account level
- Queue management for tasks waiting for accounts
"""

import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..database import AsyncSessionLocal
from ..models.account_state import AccountState, AccountStatus
from ..models.parse_task import ParseTask

logger = logging.getLogger(__name__)


class AccountManager:
    """
    Centralized manager for Telegram accounts used in parsing.
    
    Ensures proper account-level task distribution and handles FloodWait isolation.
    """
    
    def __init__(self):
        self.integration_service_url = "http://integration-service:8000"
        
    async def get_available_accounts(self) -> List[Dict]:
        """
        Get list of accounts that are available for new parsing tasks.
        
        Returns:
            List of account dictionaries with status information
        """
        try:
            logger.info("🔍 GET_AVAILABLE: Starting get_available_accounts")
            
            async with AsyncSessionLocal() as db_session:
                logger.info("🗃️  GET_AVAILABLE: Connecting to database")
                
                # Get all account states from database
                stmt = select(AccountState).where(
                    AccountState.status.in_([AccountStatus.FREE.value, AccountStatus.BLOCKED.value])
                )
                logger.info(f"🔍 GET_AVAILABLE: Querying AccountState with status in [{AccountStatus.FREE.value}, {AccountStatus.BLOCKED.value}]")
                
                result = await db_session.execute(stmt)
                account_states = result.scalars().all()
                logger.info(f"📊 GET_AVAILABLE: Found {len(account_states)} account states in database")
                
                # Log all found account states
                for i, acc in enumerate(account_states):
                    logger.info(f"📋 GET_AVAILABLE: Account {i+1}: id={acc.account_id}, status={acc.status}, blocked_until={acc.blocked_until}")
                
                # Filter only truly available accounts (not blocked by FloodWait)
                available_accounts = []
                for account_state in account_states:
                    is_available = account_state.is_available()
                    logger.info(f"🔍 GET_AVAILABLE: Account {account_state.account_id} is_available={is_available}")
                    
                    if is_available:
                        account_data = {
                            'account_id': account_state.account_id,
                            'session_id': account_state.session_id,
                            'status': account_state.status,
                            'last_activity': account_state.last_activity,
                            'total_tasks_completed': account_state.total_tasks_completed
                        }
                        available_accounts.append(account_data)
                        logger.info(f"✅ GET_AVAILABLE: Added available account {account_state.account_id}")
                
                logger.info(f"🟢 GET_AVAILABLE: Found {len(available_accounts)} available accounts out of {len(account_states)} total")
                return available_accounts
                
        except Exception as e:
            logger.error(f"❌ GET_AVAILABLE: Error getting available accounts: {e}")
            logger.exception("Full get_available_accounts error traceback:")
            return []
    
    async def get_account_status(self) -> Dict:
        """
        Get comprehensive status of all accounts.
        
        Returns:
            Dictionary with account statistics and detailed status
        """
        try:
            async with AsyncSessionLocal() as db_session:
                # Get all account states
                stmt = select(AccountState)
                result = await db_session.execute(stmt)
                account_states = result.scalars().all()
                
                # Categorize accounts by status
                status_counts = {
                    'free': 0,
                    'busy': 0, 
                    'blocked': 0,
                    'error': 0,
                    'total': len(account_states)
                }
                
                account_details = []
                for account_state in account_states:
                    # Update status if FloodWait expired
                    if account_state.is_blocked() and account_state.blocked_until and datetime.utcnow() >= account_state.blocked_until:
                        account_state.status = AccountStatus.FREE.value
                        account_state.blocked_until = None
                        await db_session.commit()
                    
                    # Count by status
                    if account_state.status == AccountStatus.FREE.value:
                        status_counts['free'] += 1
                    elif account_state.status == AccountStatus.BUSY.value:
                        status_counts['busy'] += 1
                    elif account_state.status == AccountStatus.BLOCKED.value:
                        status_counts['blocked'] += 1
                    elif account_state.status == AccountStatus.ERROR.value:
                        status_counts['error'] += 1
                    
                    # Add detailed account info
                    account_details.append({
                        'account_id': account_state.account_id,
                        'status': account_state.status,
                        'current_task_id': account_state.current_task_id,
                        'time_until_unblocked': account_state.time_until_unblocked(),
                        'last_activity': account_state.last_activity.isoformat() if account_state.last_activity else None,
                        'total_tasks_completed': account_state.total_tasks_completed,
                        'total_flood_waits': account_state.total_flood_waits,
                        'error_message': account_state.error_message
                    })
                
                return {
                    'status_counts': status_counts,
                    'accounts': account_details,
                    'updated_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting account status: {e}")
            return {
                'status_counts': {'free': 0, 'busy': 0, 'blocked': 0, 'error': 0, 'total': 0},
                'accounts': [],
                'updated_at': datetime.utcnow().isoformat(),
                'error': str(e)
            }

    async def assign_task_to_account(self, task_id: str) -> Optional[str]:
        """
        Assign a parsing task to an available account.
        
        Args:
            task_id: ID of the task to assign
            
        Returns:
            Account ID if assignment successful, None if no accounts available
        """
        try:
            async with AsyncSessionLocal() as db_session:
                # Find available account (not blocked, not busy)
                stmt = select(AccountState).where(
                    AccountState.status == AccountStatus.FREE.value,
                    (AccountState.blocked_until.is_(None)) | (AccountState.blocked_until <= datetime.utcnow())
                ).order_by(AccountState.last_activity.asc())  # Prefer least recently used
                
                result = await db_session.execute(stmt)
                account_state = result.scalars().first()
                
                if not account_state:
                    logger.warning(f"⚠️ No available accounts for task {task_id}")
                    return None
                
                # Assign task to account
                account_state.assign_task(task_id)
                await db_session.commit()
                
                logger.info(f"✅ Assigned task {task_id} to account {account_state.account_id}")
                return account_state.account_id
                
        except Exception as e:
            logger.error(f"❌ Error assigning task {task_id} to account: {e}")
            return None

    async def free_account_from_task(self, task_id: str):
        """
        Free an account after task completion.
        
        Args:
            task_id: ID of the completed task
        """
        try:
            async with AsyncSessionLocal() as db_session:
                # Find account assigned to this task
                stmt = select(AccountState).where(AccountState.current_task_id == task_id)
                result = await db_session.execute(stmt)
                account_state = result.scalars().first()
                
                if account_state:
                    account_state.complete_task()
                    await db_session.commit()
                    logger.info(f"✅ Freed account {account_state.account_id} from completed task {task_id}")
                else:
                    logger.warning(f"⚠️ No account found for task {task_id}")
                    
        except Exception as e:
            logger.error(f"❌ Error freeing account from task {task_id}: {e}")

    async def handle_flood_wait(self, account_id: str, seconds: int, error_message: str = None):
        """
        Handle FloodWait error for a specific account.
        
        Args:
            account_id: ID of the affected account
            seconds: How long to block the account
            error_message: Optional error message
        """
        try:
            async with AsyncSessionLocal() as db_session:
                # Find account state
                stmt = select(AccountState).where(AccountState.account_id == account_id)
                result = await db_session.execute(stmt)
                account_state = result.scalars().first()
                
                if account_state:
                    # Free current task if any (it will be reassigned to another account)
                    current_task = account_state.current_task_id
                    account_state.block_for_flood_wait(seconds, error_message)
                    await db_session.commit()
                    
                    logger.warning(f"⏳ Account {account_id} blocked for {seconds}s due to FloodWait")
                    
                    # If account had a task, try to reassign it to another account
                    if current_task:
                        logger.info(f"🔄 Attempting to reassign task {current_task} to another account")
                        new_account = await self.assign_task_to_account(current_task)
                        if new_account:
                            logger.info(f"✅ Reassigned task {current_task} to account {new_account}")
                        else:
                            logger.warning(f"⚠️ No available accounts to reassign task {current_task}")
                else:
                    logger.error(f"❌ Account {account_id} not found for FloodWait handling")
                    
        except Exception as e:
            logger.error(f"❌ Error handling FloodWait for account {account_id}: {e}")

    async def sync_accounts_from_integration_service(self):
        """
        Synchronize account states with integration-service data.
        
        Creates new AccountState records for accounts from integration-service
        that don't exist in our database yet.
        """
        try:
            logger.info("🔄 SYNC: Starting sync_accounts_from_integration_service")
            
            # Get accounts from integration-service
            async with aiohttp.ClientSession() as session:
                url = f"{self.integration_service_url}/api/v1/telegram/internal/active-accounts"
                logger.info(f"🌐 SYNC: Making request to {url}")
                
                async with session.get(url) as response:
                    logger.info(f"📡 SYNC: Response status: {response.status}")
                    
                    if response.status != 200:
                        logger.error(f"❌ SYNC: Failed to get accounts from integration-service: {response.status}")
                        return
                    
                    integration_accounts = await response.json()
                    logger.info(f"📥 SYNC: Received {len(integration_accounts)} accounts from integration-service")
            
            if not integration_accounts:
                logger.warning("⚠️ SYNC: No accounts received from integration-service")
                return
            
            # Log first account for debugging
            if integration_accounts:
                logger.info(f"🔍 SYNC: Sample account data: {integration_accounts[0]}")
            
            # Sync with database
            async with AsyncSessionLocal() as db_session:
                logger.info("🗃️  SYNC: Connecting to database")
                
                # Get existing account states
                stmt = select(AccountState)
                result = await db_session.execute(stmt)
                existing_accounts = {acc.account_id: acc for acc in result.scalars().all()}
                logger.info(f"📊 SYNC: Found {len(existing_accounts)} existing accounts in database")
                
                # Create new account states for accounts not in database
                new_accounts_created = 0
                accounts_processed = 0
                
                for integration_account in integration_accounts:
                    accounts_processed += 1
                    account_id = str(integration_account.get('id') or integration_account.get('session_id'))
                    logger.info(f"🔄 SYNC: Processing account {accounts_processed}/{len(integration_accounts)}: {account_id}")
                    
                    if account_id not in existing_accounts:
                        logger.info(f"➕ SYNC: Creating new AccountState for {account_id}")
                        
                        try:
                            # Create new account state
                            new_account_state = AccountState(
                                account_id=account_id,
                                session_id=integration_account.get('session_id'),
                                status=AccountStatus.FREE.value,
                                account_info=str(integration_account)  # Store full account info
                            )
                            db_session.add(new_account_state)
                            new_accounts_created += 1
                            logger.info(f"✅ SYNC: Added AccountState for {account_id}")
                            
                        except Exception as create_error:
                            logger.error(f"❌ SYNC: Error creating AccountState for {account_id}: {create_error}")
                            continue
                    else:
                        logger.info(f"⏭️  SYNC: Account {account_id} already exists in database")
                
                if new_accounts_created > 0:
                    logger.info(f"💾 SYNC: Committing {new_accounts_created} new accounts to database")
                    await db_session.commit()
                    logger.info(f"✅ SYNC: Successfully created {new_accounts_created} new account states")
                else:
                    logger.info("✅ SYNC: All integration-service accounts already synced")
                
                # Final verification
                stmt = select(AccountState)
                result = await db_session.execute(stmt)
                total_accounts_after = len(result.scalars().all())
                logger.info(f"📊 SYNC: Final count: {total_accounts_after} accounts in database")
                    
        except Exception as e:
            logger.error(f"❌ SYNC: Error syncing accounts from integration-service: {e}")
            logger.exception("Full sync error traceback:")

    async def get_task_queue_status(self) -> Dict:
        """
        Get status of task queue and account assignments.
        
        Returns:
            Dictionary with queue information
        """
        try:
            async with AsyncSessionLocal() as db_session:
                # Get pending tasks
                stmt = select(ParseTask).where(ParseTask.status == "pending")
                result = await db_session.execute(stmt)
                pending_tasks = result.scalars().all()
                
                # Get running tasks
                stmt = select(ParseTask).where(ParseTask.status == "running")
                result = await db_session.execute(stmt)
                running_tasks = result.scalars().all()
                
                # Get busy accounts
                stmt = select(AccountState).where(AccountState.status == AccountStatus.BUSY.value)
                result = await db_session.execute(stmt)
                busy_accounts = result.scalars().all()
                
                return {
                    'pending_tasks': len(pending_tasks),
                    'running_tasks': len(running_tasks),
                    'busy_accounts': len(busy_accounts),
                    'pending_task_ids': [task.task_id for task in pending_tasks],
                    'running_assignments': {
                        account.account_id: account.current_task_id 
                        for account in busy_accounts 
                        if account.current_task_id
                    },
                    'updated_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting task queue status: {e}")
            return {
                'pending_tasks': 0,
                'running_tasks': 0,
                'busy_accounts': 0,
                'pending_task_ids': [],
                'running_assignments': {},
                'updated_at': datetime.utcnow().isoformat(),
                'error': str(e)
            }


# Global instance
account_manager = AccountManager() 