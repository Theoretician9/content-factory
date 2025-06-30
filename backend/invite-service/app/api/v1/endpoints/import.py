from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, List, Optional, Any
import csv
import json
import io
import logging
from datetime import datetime
import httpx

from app.core.database import get_db
from app.models.invite_task import InviteTask
from app.models.invite_target import InviteTarget
from app.schemas.target import InviteTargetCreate
from app.core.auth import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/tasks/{task_id}/import/file")
async def import_targets_from_file(
    task_id: int,
    file: UploadFile = File(...),
    source_name: str = Form("file_upload"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Импорт целевой аудитории из CSV/JSON файла
    """
    # Проверяем доступ к задаче
    task_query = select(InviteTask).where(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    )
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Проверяем тип файла
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_extension = file.filename.lower().split('.')[-1]
    if file_extension not in ['csv', 'json', 'txt']:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use CSV, JSON or TXT")
    
    try:
        # Читаем содержимое файла
        content = await file.read()
        content_str = content.decode('utf-8')
        
        imported_targets = []
        errors = []
        
        if file_extension == 'csv':
            imported_targets, errors = await _parse_csv_content(content_str)
        elif file_extension == 'json':
            imported_targets, errors = await _parse_json_content(content_str)
        elif file_extension == 'txt':
            imported_targets, errors = await _parse_txt_content(content_str)
        
        if not imported_targets and errors:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {'; '.join(errors[:5])}")
        
        # Сохраняем цели в базу данных
        saved_targets = []
        for target_data in imported_targets:
            try:
                target = InviteTarget(
                    task_id=task_id,
                    username=target_data.get('username'),
                    phone_number=target_data.get('phone_number'),
                    user_id_platform=target_data.get('user_id_platform'),
                    email=target_data.get('email'),
                    full_name=target_data.get('full_name'),
                    source="file_import",
                    extra_data={
                        "source_file": file.filename,
                        "source_name": source_name,
                        "imported_at": datetime.utcnow().isoformat()
                    }
                )
                db.add(target)
                saved_targets.append(target)
            except Exception as e:
                errors.append(f"Failed to save target {target_data}: {str(e)}")
        
        # Обновляем счетчик целей в задаче
        task.target_count = len(saved_targets)
        
        await db.commit()
        
        logger.info(f"Импортировано {len(saved_targets)} целей для задачи {task_id} из файла {file.filename}")
        
        return {
            "success": True,
            "imported_count": len(saved_targets),
            "error_count": len(errors),
            "total_processed": len(imported_targets) + len(errors),
            "file_name": file.filename,
            "source_name": source_name,
            "errors": errors[:10] if errors else []  # Показываем только первые 10 ошибок
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding not supported. Use UTF-8")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error importing file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.post("/tasks/{task_id}/import/parsing")
async def import_targets_from_parsing(
    task_id: int,
    parsing_task_id: str,
    source_name: str = "parsing_import",
    limit: Optional[int] = Query(None, description="Limit number of targets to import"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Импорт целевой аудитории из результатов parsing-service
    """
    # Проверяем доступ к задаче
    task_query = select(InviteTask).where(
        InviteTask.id == task_id,
        InviteTask.user_id == user_id
    )
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    try:
        # Получаем JWT токен для аутентификации в parsing-service
        token = await _get_jwt_token_for_parsing_service()
        
        parsing_service_url = "http://parsing-service:8000"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Сначала проверяем что задача парсинга принадлежит пользователю
            task_response = await client.get(
                f"{parsing_service_url}/tasks/{parsing_task_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if task_response.status_code == 404:
                raise HTTPException(status_code=404, detail="Parsing task not found")
            elif task_response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to verify parsing task")
            
            task_data = task_response.json()
            
            # Проверяем принадлежность пользователю
            if task_data.get('user_id') != user_id:
                raise HTTPException(status_code=404, detail="Parsing task not found")
            
            # Получаем результаты парсинга
            results_params = {}
            if limit:
                results_params['limit'] = limit
            
            results_response = await client.get(
                f"{parsing_service_url}/results/{parsing_task_id}",
                headers={"Authorization": f"Bearer {token}"},
                params=results_params
            )
            
            if results_response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to get parsing results")
            
            results_data = results_response.json()
            parsing_results = results_data.get('results', [])
            
            if not parsing_results:
                return {
                    "success": False,
                    "message": "No parsing results found for this task",
                    "parsing_task_id": parsing_task_id,
                    "imported_count": 0
                }
            
            # Конвертируем результаты парсинга в формат InviteTarget
            imported_targets = []
            errors = []
            
            for i, result in enumerate(parsing_results):
                try:
                    # Извлекаем данные из результата парсинга
                    target_data = {
                        "username": result.get('username', '').strip() or None,
                        "phone_number": result.get('author_phone', '').strip() or None,
                        "user_id_platform": result.get('platform_id', '').strip() or None,
                        "full_name": result.get('display_name', '').strip() or None,
                    }
                    
                    # Проверяем что есть хотя бы один идентификатор
                    if not any([target_data["username"], target_data["phone_number"], 
                               target_data["user_id_platform"]]):
                        errors.append(f"Result {i}: No valid identifier found")
                        continue
                    
                    # Создаем InviteTarget
                    invite_target = InviteTarget(
                        task_id=task_id,
                        username=target_data["username"],
                        phone_number=target_data["phone_number"],
                        user_id_platform=target_data["user_id_platform"],
                        full_name=target_data["full_name"],
                        source="parsing_import",
                        extra_data={
                            "parsing_task_id": parsing_task_id,
                            "parsing_result_id": result.get('id'),
                            "source_name": source_name,
                            "imported_at": datetime.utcnow().isoformat(),
                            "original_data": result  # Сохраняем оригинальные данные
                        }
                    )
                    
                    db.add(invite_target)
                    imported_targets.append(invite_target)
                    
                except Exception as e:
                    errors.append(f"Result {i}: {str(e)}")
                    logger.error(f"Error processing parsing result {i}: {e}")
            
            # Обновляем счетчик целей в задаче (добавляем к существующему)
            current_count_query = select(InviteTarget).where(InviteTarget.task_id == task_id)
            current_count_result = await db.execute(current_count_query)
            current_targets = current_count_result.scalars().all()
            
            task.target_count = len(current_targets) + len(imported_targets)
            task.updated_at = datetime.utcnow()
            
            await db.commit()
            
            logger.info(f"Импортировано {len(imported_targets)} целей из задачи парсинга {parsing_task_id} для задачи {task_id}")
            
            return {
                "success": True,
                "message": f"Successfully imported {len(imported_targets)} targets from parsing results",
                "parsing_task_id": parsing_task_id,
                "task_id": task_id,
                "imported_count": len(imported_targets),
                "error_count": len(errors),
                "total_processed": len(parsing_results),
                "errors": errors[:10] if errors else [],  # Показываем только первые 10 ошибок
                "source_name": source_name,
                "parsing_task_title": task_data.get('title', 'Unknown'),
                "parsing_platform": task_data.get('platform', 'telegram')
            }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error importing from parsing-service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Parsing import failed: {str(e)}")

@router.post("/import/validate")
async def validate_import_data(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id)
):
    """
    Валидация данных импорта без сохранения
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_extension = file.filename.lower().split('.')[-1]
    if file_extension not in ['csv', 'json', 'txt']:
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        if file_extension == 'csv':
            targets, errors = await _parse_csv_content(content_str)
        elif file_extension == 'json':
            targets, errors = await _parse_json_content(content_str)
        elif file_extension == 'txt':
            targets, errors = await _parse_txt_content(content_str)
        
        # Анализ качества данных
        stats = {
            "total_records": len(targets) + len(errors),
            "valid_records": len(targets),
            "invalid_records": len(errors),
            "has_usernames": sum(1 for t in targets if t.get('username')),
            "has_phones": sum(1 for t in targets if t.get('phone_number')),
            "has_emails": sum(1 for t in targets if t.get('email')),
            "has_user_ids": sum(1 for t in targets if t.get('user_id_platform'))
        }
        
        return {
            "file_name": file.filename,
            "file_size": len(content),
            "validation_result": "valid" if targets and not errors else "invalid",
            "statistics": stats,
            "sample_records": targets[:5],  # Первые 5 записей для предпросмотра
            "errors": errors[:10] if errors else []
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding not supported. Use UTF-8")
    except Exception as e:
        logger.error(f"Error validating file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

# Вспомогательные функции парсинга

async def _parse_csv_content(content: str) -> tuple[List[Dict], List[str]]:
    """Парсинг CSV содержимого"""
    targets = []
    errors = []
    
    try:
        csv_reader = csv.DictReader(io.StringIO(content))
        
        for row_num, row in enumerate(csv_reader, start=2):  # Начинаем с 2 из-за заголовка
            try:
                target = {}
                
                # Гибкое сопоставление столбцов
                for key, value in row.items():
                    if not value or not value.strip():
                        continue
                        
                    key_lower = key.lower().strip()
                    value_clean = value.strip()
                    
                    if key_lower in ['username', 'user', 'login', 'nickname']:
                        target['username'] = value_clean
                    elif key_lower in ['phone', 'phone_number', 'telephone', 'mobile']:
                        target['phone_number'] = value_clean
                    elif key_lower in ['email', 'mail', 'email_address']:
                        target['email'] = value_clean
                    elif key_lower in ['user_id', 'id', 'user_id_platform', 'platform_id']:
                        target['user_id_platform'] = value_clean
                    elif key_lower in ['name', 'full_name', 'fullname', 'display_name']:
                        target['full_name'] = value_clean
                
                if target:  # Если хотя бы одно поле заполнено
                    targets.append(target)
                else:
                    errors.append(f"Row {row_num}: No valid data found")
                    
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                
    except Exception as e:
        errors.append(f"CSV parsing error: {str(e)}")
    
    return targets, errors

async def _parse_json_content(content: str) -> tuple[List[Dict], List[str]]:
    """Парсинг JSON содержимого"""
    targets = []
    errors = []
    
    try:
        data = json.loads(content)
        
        if isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    target = {}
                    if item.get('username'):
                        target['username'] = str(item['username']).strip()
                    if item.get('phone_number') or item.get('phone'):
                        target['phone_number'] = str(item.get('phone_number') or item.get('phone')).strip()
                    if item.get('email'):
                        target['email'] = str(item['email']).strip()
                    if item.get('user_id_platform') or item.get('user_id'):
                        target['user_id_platform'] = str(item.get('user_id_platform') or item.get('user_id')).strip()
                    if item.get('full_name') or item.get('name'):
                        target['full_name'] = str(item.get('full_name') or item.get('name')).strip()
                    
                    if target:
                        targets.append(target)
                    else:
                        errors.append(f"Item {i}: No valid data found")
                else:
                    errors.append(f"Item {i}: Expected object, got {type(item)}")
        else:
            errors.append("Expected JSON array")
            
    except json.JSONDecodeError as e:
        errors.append(f"JSON parsing error: {str(e)}")
    except Exception as e:
        errors.append(f"Unexpected error: {str(e)}")
    
    return targets, errors

async def _parse_txt_content(content: str) -> tuple[List[Dict], List[str]]:
    """Парсинг TXT содержимого (одно значение на строку)"""
    targets = []
    errors = []
    
    lines = content.strip().split('\n')
    
    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
            
        target = {}
        
        # Определяем тип данных по формату
        if '@' in line and '.' in line:
            target['email'] = line
        elif line.startswith('+') or line.replace('-', '').replace(' ', '').isdigit():
            target['phone_number'] = line
        elif line.isdigit():
            target['user_id_platform'] = line
        else:
            target['username'] = line
        
        if target:
            targets.append(target)
        else:
            errors.append(f"Line {line_num}: Unrecognized format")
    
    return targets, errors

async def _get_jwt_token_for_parsing_service() -> str:
    """Получение JWT токена для межсервисного взаимодействия с Parsing Service"""
    try:
        from app.core.vault import get_vault_client
        from datetime import datetime, timedelta
        
        vault_client = get_vault_client()
        secret_data = vault_client.get_secret("jwt")
        
        if not secret_data or 'secret_key' not in secret_data:
            raise Exception("JWT secret not found in Vault")
        
        # Создаем токен для invite-service
        payload = {
            'service': 'invite-service',
            'user_id': 1,  # Системный токен
            'exp': int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        
        import jwt
        token = jwt.encode(payload, secret_data['secret_key'], algorithm='HS256')
        return token
        
    except Exception as e:
        logger.error(f"Error getting JWT token for parsing service: {e}")
        raise 