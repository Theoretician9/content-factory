#!/usr/bin/env python3
"""
Скрипт для очистки всех задач в parsing и invite сервисах
"""

import asyncio
import httpx
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def clear_parsing_service_tasks():
    """Очистка задач в parsing service"""
    try:
        logger.info("🧹 Clearing parsing service tasks...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.delete("http://localhost:8002/admin/clear-all-tasks")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Parsing service: {result['message']}")
                logger.info(f"📊 Details: {json.dumps(result['details'], indent=2)}")
                return result
            else:
                logger.error(f"❌ Parsing service failed: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}", "details": response.text}
                
    except Exception as e:
        logger.error(f"❌ Error clearing parsing service: {e}")
        return {"error": str(e)}

async def clear_invite_service_tasks():
    """Очистка задач в invite service"""
    try:
        logger.info("🧹 Clearing invite service tasks...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.delete("http://localhost:8003/admin/clear-all-tasks")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Invite service: {result['message']}")
                logger.info(f"📊 Details: {json.dumps(result['details'], indent=2)}")
                return result
            else:
                logger.error(f"❌ Invite service failed: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}", "details": response.text}
                
    except Exception as e:
        logger.error(f"❌ Error clearing invite service: {e}")
        return {"error": str(e)}

async def check_account_manager_status():
    """Проверка статуса Account Manager"""
    try:
        logger.info("🔍 Checking Account Manager status...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check account status
            response = await client.get("http://localhost:8000/api/v1/account-manager/status")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"📊 Account Manager status: {json.dumps(result, indent=2)}")
                return result
            else:
                logger.warning(f"⚠️ Account Manager status check failed: {response.status_code}")
                return None
                
    except Exception as e:
        logger.warning(f"⚠️ Error checking Account Manager: {e}")
        return None

async def main():
    """Главная функция"""
    logger.info("🚀 Starting task clearing process...")
    
    # 1. Check initial status
    initial_status = await check_account_manager_status()
    
    # 2. Clear parsing service tasks
    parsing_result = await clear_parsing_service_tasks()
    
    # 3. Clear invite service tasks
    invite_result = await clear_invite_service_tasks()
    
    # 4. Check final status
    await asyncio.sleep(2)  # Wait a bit for changes to propagate
    final_status = await check_account_manager_status()
    
    # 5. Summary
    logger.info("📋 SUMMARY:")
    logger.info(f"  Parsing service: {'✅ Success' if parsing_result.get('success') else '❌ Failed'}")
    logger.info(f"  Invite service: {'✅ Success' if invite_result.get('success') else '❌ Failed'}")
    
    if initial_status and final_status:
        logger.info("📊 Account status change:")
        logger.info(f"  Before: {initial_status.get('total_accounts', 'Unknown')} accounts")
        logger.info(f"  After: {final_status.get('total_accounts', 'Unknown')} accounts")
    
    return {
        "parsing_result": parsing_result,
        "invite_result": invite_result,
        "initial_status": initial_status,
        "final_status": final_status
    }

if __name__ == "__main__":
    asyncio.run(main())