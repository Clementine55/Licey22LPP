from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
import requests
import subprocess
import re
import logging

from core.config import settings
from schemas.print_models import PrintRequest
from services import OnlyOfficeService

logger = logging.getLogger("PrintPortal")
router = APIRouter(tags=["Печать CUPS"])

@router.post("/print")
def print_document(req: PrintRequest, background_tasks: BackgroundTasks):
    try:
        ADMIN_HEADERS = {"Authorization": f"Token {settings.SEAFILE_ADMIN_TOKEN}"}
        download_url = requests.get(f"{settings.SERVER_URL}/api2/repos/{req.repo_id}/file/?p={req.file_path}", headers=ADMIN_HEADERS).text.strip('"')
        pdf_path = OnlyOfficeService.convert(download_url, req.file_path, req.orientation, req.margins, req.scale, req.paper_size, settings.DOWNLOADS_DIR)

        cmd = ["lp", "-d", req.printer_name, "-n", str(req.copies), "-o", f"media={req.paper_size.upper()}"]
        
        if req.pages and req.pages.lower() not in ["all", "все", ""]:
            safe_pages = "".join(c for c in req.pages if c.isdigit() or c in "-,")
            if safe_pages: cmd.extend(["-P", safe_pages])
                
        cmd.extend(["-o", f"sides={req.duplex}"]) if req.duplex != "none" else cmd.extend(["-o", "sides=one-sided"])
        cmd.append(pdf_path)

        subprocess.run(cmd, check=True)
        return {"status": "ok", "message": "Документ успешно отправлен"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка системы печати CUPS: {e}")
        raise HTTPException(status_code=500, detail="Ошибка отправки на принтер")
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Ошибка печати")

@router.get("/printers")
def get_printers():
    try:
        result = subprocess.run(["lpstat", "-v"], capture_output=True, text=True, check=True)
        printers = []
        for line in result.stdout.split('\n'):
            if line.startswith("device for "):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    name_part = parts[0].replace("device for ", "").strip()
                    uri_part = parts[1].strip()
                    if not uri_part.startswith("usb://"):
                        printers.append(name_part)
        return {"printers": printers}
    except Exception as e:
        logger.error(f"Ошибка получения списка принтеров: {e}")
        return {"printers": []}

@router.get("/printer/{printer_name}/status")
def get_printer_status(printer_name: str):
    try:
        res_v = subprocess.run(["lpstat", "-v", printer_name], capture_output=True, text=True)
        uri = res_v.stdout.split(":", 1)[1].strip() if res_v.stdout and "device for" in res_v.stdout else ""
        
        if uri.startswith(("socket://", "lpd://", "ipp://", "http://", "https://")):
            match = re.search(r'://([^/:]+)', uri)
            if match:
                ping_res = subprocess.run(["ping", "-c", "1", "-W", "1", match.group(1)], capture_output=True)
                if ping_res.returncode != 0: return {"status": "error", "message": "🔴 Принтер отключен от сети"}

        result = subprocess.run(["lpstat", "-p", printer_name], capture_output=True, text=True)
        output = result.stdout.lower()
        
        if any(state in output for state in ["disabled", "not connected", "unplugged"]): return {"status": "error", "message": "🔴 Выключен или недоступен"}
        elif "printing" in output: return {"status": "ok", "message": "🟡 Печатает..."}
        elif "idle" in output: return {"status": "ok", "message": "🟢 Готов к печати"}
        else: return {"status": "unknown", "message": "⚪ Статус неизвестен"}
    except Exception as e:
        logger.error(f"Ошибка проверки статуса принтера: {e}")
        return {"status": "error", "message": "🔴 Ошибка сервера печати"}