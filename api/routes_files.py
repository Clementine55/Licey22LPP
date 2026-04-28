from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from fastapi.responses import FileResponse
import requests
import os
import uuid
import mimetypes
import logging

from core.config import settings
from services import OnlyOfficeService, PDFService, cleanup_temp_files

logger = logging.getLogger("PrintPortal")
router = APIRouter(tags=["Файлы и Предпросмотр"])

ADMIN_HEADERS = {"Authorization": f"Token {settings.SEAFILE_ADMIN_TOKEN}"}

@router.get("/libraries")
def get_libraries(
    username: str = Header(..., alias="X-Authentik-Username"),
    email: str = Header("", alias="X-Authentik-Email")
):
    try:
        seafile_user = email if email else f"{username}@licey22.local"
        
        url = f"{settings.SERVER_URL}/api/v2.1/admin/libraries/?owner={seafile_user}"
        resp = requests.get(url, headers=ADMIN_HEADERS)
        
        if resp.status_code != 200:
            logger.warning(f"Seafile API вернул ошибку {resp.status_code}. Ответ: {resp.text}")
            return {"libraries": []}

        data = resp.json()
        # Seafile v2.1 возвращает словарь {"data": [...]}, распаковываем его
        repos = data.get("data", []) if isinstance(data, dict) else data
        
        libraries = [{"id": r['id'], "name": r['name'], "category": "Личная библиотека"} for r in repos]
        return {"libraries": libraries}
    except Exception as e:
        logger.error(f"Ошибка получения библиотек: {e}")
        return {"libraries": []}
        
@router.get("/libraries")
def get_libraries(
    username: str = Header(..., alias="X-Authentik-Username")
):
    try:
        seafile_user = f"{username}@licey22.local"
        
        url = f"{settings.SERVER_URL}/api/v2.1/admin/libraries/?owner={seafile_user}"
        resp = requests.get(url, headers=ADMIN_HEADERS)
        
        if resp.status_code != 200:
            logger.warning(f"Seafile API вернул ошибку {resp.status_code}. Ответ: {resp.text}")
            return {"libraries": []}

        data = resp.json()
        repos = data.get("data", []) if isinstance(data, dict) else data
        
        libraries = [{"id": r['id'], "name": r['name'], "category": "Личная библиотека"} for r in repos]
        return {"libraries": libraries}
    except Exception as e:
        logger.error(f"Ошибка получения библиотек: {e}")
        return {"libraries": []}
        
@router.get("/directory")
def get_directory(repo_id: str, path: str = "/"):
    try:
        url = f"{settings.SERVER_URL}/api/v2.1/admin/libraries/{repo_id}/dirents/?parent_dir={path}"
        resp = requests.get(url, headers=ADMIN_HEADERS)
        
        if resp.status_code != 200:
            return {"path": path, "content": []}
            
        items = resp.json()
        folders = [{"name": i['name'], "type": "dir"} for i in items if i['type'] == 'dir']
        files = [{"name": i['name'], "type": "file", "size_kb": round(i.get('size', 0)/1024, 1)} for i in items if i['type'] == 'file']
        return {"path": path, "content": folders + files}
    except Exception as e:
        logger.error(f"Ошибка чтения директории: {e}")
        return {"path": path, "content": []}