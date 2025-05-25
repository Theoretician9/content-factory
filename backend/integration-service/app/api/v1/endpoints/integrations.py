from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from app.core.config import get_vault_client
from app.core.vault import IntegrationVaultClient

router = APIRouter()

@router.get("/platforms", response_model=List[str])
async def list_platforms(
    vault: IntegrationVaultClient = Depends(get_vault_client)
) -> List[str]:
    """
    Получить список доступных платформ
    """
    try:
        return vault.list_integrations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/platforms/{platform}", response_model=Dict[str, Any])
async def get_platform_credentials(
    platform: str,
    vault: IntegrationVaultClient = Depends(get_vault_client)
) -> Dict[str, Any]:
    """
    Получить учетные данные для платформы
    """
    try:
        return vault.get_integration_credentials(platform)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Platform {platform} not found")

@router.put("/platforms/{platform}")
async def update_platform_credentials(
    platform: str,
    credentials: Dict[str, Any],
    vault: IntegrationVaultClient = Depends(get_vault_client)
) -> Dict[str, str]:
    """
    Обновить учетные данные для платформы
    """
    try:
        vault.update_integration_credentials(platform, credentials)
        return {"status": "success", "message": f"Credentials for {platform} updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/platforms/{platform}")
async def delete_platform_credentials(
    platform: str,
    vault: IntegrationVaultClient = Depends(get_vault_client)
) -> Dict[str, str]:
    """
    Удалить учетные данные платформы
    """
    try:
        vault.delete_integration_credentials(platform)
        return {"status": "success", "message": f"Credentials for {platform} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 