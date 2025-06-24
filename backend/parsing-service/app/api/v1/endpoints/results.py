"""Parse results API endpoints."""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from typing import List, Optional
import json
import csv
import io

router = APIRouter()

# Временное хранилище результатов (в реальной версии будет PostgreSQL)
task_results = {}

@router.get("/")
async def list_results():
    """List all parsing results."""
    return {
        "results": list(task_results.values()),
        "total": len(task_results),
        "status": "active"
    }

@router.get("/{task_id}")
async def get_result(
    task_id: str,
    format: Optional[str] = "json",
    platform_filter: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0
):
    """Get parsing results for specific task."""
    # Генерируем mock результаты для задачи если их ещё нет
    if task_id not in task_results:
        task_results[task_id] = generate_mock_results(task_id)
    
    results = task_results[task_id]
    
    # Применяем фильтры
    if platform_filter:
        results = [r for r in results if r.get("platform") == platform_filter]
    
    # Применяем пагинацию
    paginated_results = results[offset:offset + limit]
    
    return {
        "task_id": task_id,
        "results": paginated_results,
        "total": len(results),
        "format": format,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < len(results)
        }
    }

@router.get("/{task_id}/export")
async def export_result(task_id: str, format: str = "json"):
    """Export parsing result in specified format."""
    # Получаем результаты
    if task_id not in task_results:
        task_results[task_id] = generate_mock_results(task_id)
    
    results = task_results[task_id]
    
    if not results:
        raise HTTPException(status_code=404, detail="No results found for this task")
    
    # Экспорт в JSON
    if format.lower() == "json":
        json_content = json.dumps(results, ensure_ascii=False, indent=2)
        return StreamingResponse(
            io.BytesIO(json_content.encode('utf-8')),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=parsing_results_{task_id}.json"}
        )
    
    # Экспорт в CSV
    elif format.lower() == "csv":
        output = io.StringIO()
        if results:
            # Определяем все ключи для CSV заголовков
            all_keys = set()
            for result in results:
                all_keys.update(result.keys())
                if result.get("platform_specific_data"):
                    all_keys.update(f"specific_{k}" for k in result["platform_specific_data"].keys())
            
            writer = csv.DictWriter(output, fieldnames=sorted(all_keys))
            writer.writeheader()
            
            for result in results:
                # Развернуть platform_specific_data
                row = result.copy()
                if result.get("platform_specific_data"):
                    for k, v in result["platform_specific_data"].items():
                        row[f"specific_{k}"] = v
                    del row["platform_specific_data"]
                writer.writerow(row)
        
        csv_content = output.getvalue()
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=parsing_results_{task_id}.csv"}
        )
    
    # Экспорт в NDJSON (newline-delimited JSON)
    elif format.lower() == "ndjson":
        ndjson_lines = [json.dumps(result, ensure_ascii=False) for result in results]
        ndjson_content = "\n".join(ndjson_lines)
        return StreamingResponse(
            io.BytesIO(ndjson_content.encode('utf-8')),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f"attachment; filename=parsing_results_{task_id}.ndjson"}
        )
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use 'json', 'csv', or 'ndjson'")

def generate_mock_results(task_id: str) -> List[dict]:
    """Генерируем mock результаты для демонстрации."""
    import uuid
    from datetime import datetime, timedelta
    import random
    
    results = []
    num_results = random.randint(20, 100)  # Случайное количество результатов
    
    # Примеры Telegram пользователей
    sample_users = [
        {"username": "john_doe", "first_name": "John", "last_name": "Doe"},
        {"username": "alice_smith", "first_name": "Alice", "last_name": "Smith"},
        {"username": "bob_johnson", "first_name": "Bob", "last_name": "Johnson"},
        {"username": "emma_brown", "first_name": "Emma", "last_name": "Brown"},
        {"username": "mike_wilson", "first_name": "Mike", "last_name": "Wilson"},
        {"username": "sarah_davis", "first_name": "Sarah", "last_name": "Davis"},
        {"username": "chris_taylor", "first_name": "Chris", "last_name": "Taylor"},
        {"username": "lisa_anderson", "first_name": "Lisa", "last_name": "Anderson"}
    ]
    
    for i in range(num_results):
        user = random.choice(sample_users)
        created_time = datetime.utcnow() - timedelta(days=random.randint(0, 30))
        
        result = {
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "platform": "telegram",
            "platform_id": str(random.randint(100000000, 999999999)),
            "username": user.get("username"),
            "display_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            "author_phone": f"+1{random.randint(1000000000, 9999999999)}" if random.random() > 0.6 else None,  # 40% имеют открытые номера
            "created_at": created_time.isoformat(),
            "platform_specific_data": {
                "user_id": random.randint(100000000, 999999999),
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "language_code": random.choice(["en", "ru", "es", "de"]),
                "is_bot": False,
                "is_premium": random.choice([True, False]),
                "last_seen": "recently" if random.random() > 0.3 else "long_time_ago",
                "phone_number": f"+1{random.randint(1000000000, 9999999999)}" if random.random() > 0.7 else None,
                "bio": f"User bio for {user.get('first_name')}" if random.random() > 0.5 else None
            }
        }
        results.append(result)
    
    return results
