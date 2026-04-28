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
        
        # ПРАВИЛЬНЫЙ АДМИНСКИЙ ЭНДПОИНТ: поиск библиотек по владельцу
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
        
@router.get("/directory")
def get_directory(repo_id: str, path: str = "/"):
    resp = requests.get(f"{settings.SERVER_URL}/api2/repos/{repo_id}/dir/?p={path}", headers=ADMIN_HEADERS)
    items = resp.json()
    folders = [{"name": i['name'], "type": "dir"} for i in items if i['type'] == 'dir']
    files = [{"name": i['name'], "type": "file", "size_kb": round(i.get('size', 0)/1024, 1)} for i in items if i['type'] == 'file']
    return {"path": path, "content": folders + files}

@router.get("/preview")
def get_preview(repo_id: str, file_path: str, background_tasks: BackgroundTasks, paper_size: str = "a4", orientation: str="portrait", margins: str="default", scale: str="fit", pages: str="all"):
    try:
        download_url = requests.get(f"{settings.SERVER_URL}/api2/repos/{repo_id}/file/?p={file_path}", headers=ADMIN_HEADERS).text.strip('"')
        
        pdf_path = OnlyOfficeService.convert(download_url, file_path, orientation, margins, scale, paper_size, settings.DOWNLOADS_DIR)
        cropped_path = os.path.join(settings.DOWNLOADS_DIR, f"crop_{uuid.uuid4().hex}.pdf")
        final_pdf = PDFService.extract_pages(pdf_path, pages, cropped_path)
        
        background_tasks.add_task(cleanup_temp_files, pdf_path, cropped_path)
        mime_type, _ = mimetypes.guess_type(final_pdf)
        return FileResponse(final_pdf, media_type=mime_type or "application/octet-stream")
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Ошибка предпросмотра")