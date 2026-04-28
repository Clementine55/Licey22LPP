from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Depends
from fastapi.responses import FileResponse
import httpx
import os
import uuid
import mimetypes
import logging

from core.config import settings
from services import OnlyOfficeService, PDFService, cleanup_temp_files
from .routes_auth import get_real_seafile_token

logger = logging.getLogger("PrintPortal")
router = APIRouter(tags=["Файлы и Предпросмотр"])

@router.get("/libraries")
async def get_libraries(real_token: str = Depends(get_real_seafile_token)):
    if not real_token:
        raise HTTPException(status_code=401, detail="Ошибка авторизации Seafile")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{settings.SERVER_URL}/api2/repos/", 
                headers={"Authorization": f"Token {real_token}"}
            )
            repos = resp.json()
            libraries = []
            for r in repos:
                repo_type = r.get('type', 'repo')
                if repo_type == 'repo': category = "Мои библиотеки"
                elif repo_type == 'srepo': category = "Доступные мне"
                elif repo_type == 'grepo': category = r.get('group_name', 'Общее со всеми')
                else: category = "Прочее"
                libraries.append({"id": r['id'], "name": r['name'], "category": category})
            return {"libraries": libraries}
    except Exception as e:
        logger.error(f"Ошибка получения библиотек: {e}")
        return {"libraries": []}
        
@router.get("/directory")
async def get_directory(repo_id: str, path: str = "/", real_token: str = Depends(get_real_seafile_token)):
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.SERVER_URL}/api2/repos/{repo_id}/dir/?p={path}", 
            headers={"Authorization": f"Token {real_token}"}
        )
        if resp.status_code != 200:
            return {"path": path, "content": []}
        items = resp.json()
        folders = [{"name": i['name'], "type": "dir"} for i in items if i['type'] == 'dir']
        files = [{"name": i['name'], "type": "file", "size_kb": round(i.get('size', 0)/1024, 1)} for i in items if i['type'] == 'file']
        return {"path": path, "content": folders + files}

@router.get("/preview")
async def get_preview(repo_id: str, file_path: str, background_tasks: BackgroundTasks, paper_size: str = "a4", orientation: str="portrait", margins: str="default", scale: str="fit", pages: str="all", real_token: str = Depends(get_real_seafile_token)):
    try:
        headers = {"Authorization": f"Token {real_token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            file_url_resp = await client.get(f"{settings.SERVER_URL}/api2/repos/{repo_id}/file/?p={file_path}", headers=headers)
            download_url = file_url_resp.text.strip('"')
            
            pdf_path = await OnlyOfficeService.convert(download_url, file_path, orientation, margins, scale, paper_size, settings.DOWNLOADS_DIR)
            cropped_path = os.path.join(settings.DOWNLOADS_DIR, f"crop_{uuid.uuid4().hex}.pdf")
            final_pdf = await PDFService.extract_pages(pdf_path, pages, cropped_path)
            
            background_tasks.add_task(cleanup_temp_files, pdf_path, cropped_path)
            mime_type, _ = mimetypes.guess_type(final_pdf)
            return FileResponse(final_pdf, media_type=mime_type or "application/octet-stream")
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Ошибка предпросмотра")