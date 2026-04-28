from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Depends
import httpx
import asyncio
import re
import logging
import time

from core.config import settings
from schemas.print_models import PrintRequest
from services import OnlyOfficeService
from .routes_auth import get_real_seafile_token

logger = logging.getLogger("PrintPortal")
router = APIRouter(tags=["Печать CUPS"])

_PRINTER_CACHE = {"data": [], "timestamp": 0}
CACHE_TTL = 30 # Кэшируем на 30 секунд

async def get_system_printers():
    global _PRINTER_CACHE
    if time.time() - _PRINTER_CACHE["timestamp"] < CACHE_TTL and _PRINTER_CACHE["data"]:
        return _PRINTER_CACHE["data"]

    proc = await asyncio.create_subprocess_exec(
        "lpstat", "-v", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    printers = []
    for line in stdout.decode().split('\n'):
        if line.startswith("device for "):
            name = line.split(":")[0].replace("device for ", "").strip()
            uri = line.split(":", 1)[1].strip()
            if not uri.startswith("usb://"): printers.append(name)
            
    _PRINTER_CACHE = {"data": printers, "timestamp": time.time()}
    return printers

@router.post("/print")
async def print_document(req: PrintRequest, background_tasks: BackgroundTasks, real_token: str = Depends(get_real_seafile_token)):
    valid_printers = await get_system_printers()
    if req.printer_name not in valid_printers:
        raise HTTPException(status_code=400, detail="Неверный принтер")

    try:
        headers = {"Authorization": f"Token {real_token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            file_url_resp = await client.get(f"{settings.SERVER_URL}/api2/repos/{req.repo_id}/file/?p={req.file_path}", headers=headers)
            download_url = file_url_resp.text.strip('"')
            
            pdf_path = await OnlyOfficeService.convert(download_url, req.file_path, req.orientation, req.margins, req.scale, req.paper_size, settings.DOWNLOADS_DIR)

        cmd = ["-d", req.printer_name, "-n", str(req.copies), "-o", f"media={req.paper_size.upper()}"]
        if req.pages and req.pages.lower() not in ["all", "все", ""]:
            safe_pages = "".join(c for c in req.pages if c.isdigit() or c in "-,")
            if safe_pages: cmd.extend(["-P", safe_pages])
        
        cmd.extend(["-o", f"sides={req.duplex}"]) if req.duplex != "none" else cmd.extend(["-o", "sides=one-sided"])
        cmd.append(pdf_path)

        # Асинхронный запуск процесса печати
        await asyncio.create_subprocess_exec("lp", *cmd)
        return {"status": "ok", "message": "Отправлено"}
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Ошибка печати")

@router.get("/printers")
async def get_printers():
    return {"printers": await get_system_printers()}