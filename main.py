from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import requests
import os
import re
import uuid
import time
import mimetypes
import subprocess

from pydantic import BaseModel

from dotenv import load_dotenv

import logging
from logging.handlers import RotatingFileHandler

# ИМПОРТИРУЕМ НАШИ СЕРВИСЫ ИЗ СОСЕДНЕГО ФАЙЛА
from services import OnlyOfficeService, PDFService, cleanup_temp_files

# ==========================================
# КОНФИГУРАЦИЯ И ЛОГГЕР
# ==========================================

# Загружаем переменные из .env файла
load_dotenv()

SERVER_URL = os.getenv("SERVER_URL", "https://лис.лицей22.рф")
DOWNLOADS_DIR = "temp_downloads"

os.makedirs("static", exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s')
logger = logging.getLogger("PrintPortal")

# ==========================================
# МОДЕЛИ ДАННЫХ
# ==========================================
class LoginData(BaseModel):
    username: str
    password: str

class PrintRequest(BaseModel):
    repo_id: str
    file_path: str
    printer_name: str
    pages: str = "all"
    copies: int = 1
    orientation: str = "portrait"
    margins: str = "normal" 
    paper_size: str = "a4"
    scale: str = "fit"
    duplex: str = "none"


# ==========================================
# FASTAPI ЭНДПОИНТЫ (МАРШРУТЫ)
# ==========================================
app = FastAPI(title="Единый портал печати Лицея")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_frontend(): return FileResponse("static/index.html")

@app.post("/api/login")
def login(data: LoginData):
    resp = requests.post(f"{SERVER_URL}/api2/auth-token/", data={"username": data.username, "password": data.password})
    if resp.status_code == 200: return {"token": resp.json().get('token')}
    raise HTTPException(status_code=401, detail="Неверный логин или пароль")

@app.get("/api/user")
def get_user_info(x_token: str = Header(...)):
    try:
        resp = requests.get(f"{SERVER_URL}/api2/account/info/", headers={"Authorization": f"Token {x_token}"})
        data = resp.json()
        avatar = data.get("avatar_url", "")
        if avatar.startswith("/"): avatar = SERVER_URL + avatar
        return {"name": data.get("name", data.get("email", "Пользователь")), "avatar_url": avatar}
    except Exception:
        return {"name": "Пользователь", "avatar_url": ""}

@app.get("/api/libraries")
def get_libraries(x_token: str = Header(...)):
    try:
        resp = requests.get(f"{SERVER_URL}/api2/repos/", headers={"Authorization": f"Token {x_token}"})
        repos = resp.json()
        libraries = []
        
        for r in repos:
            # Seafile отдает 'repo' для личных, 'srepo' для расшаренных и 'grepo' для групп
            repo_type = r.get('type', 'repo')
            
            if repo_type == 'repo':
                category = "Мои библиотеки"
            elif repo_type == 'srepo':
                category = "Доступные мне"
            elif repo_type == 'grepo':
                # Берем название группы. Если сервер почему-то его не отдал — пишем "Общее со всеми"
                category = r.get('group_name', 'Общее со всеми')
            else:
                category = "Прочее"
                
            libraries.append({"id": r['id'], "name": r['name'], "category": category})
            
        return {"libraries": libraries}
    except Exception as e:
        logger.error(f"Ошибка получения библиотек: {e}")
        return {"libraries": []}
        
@app.get("/api/directory")
def get_directory(repo_id: str, path: str = "/", x_token: str = Header(...)):
    resp = requests.get(f"{SERVER_URL}/api2/repos/{repo_id}/dir/?p={path}", headers={"Authorization": f"Token {x_token}"})
    items = resp.json()
    folders = [{"name": i['name'], "type": "dir"} for i in items if i['type'] == 'dir']
    files = [{"name": i['name'], "type": "file", "size_kb": round(i.get('size', 0)/1024, 1)} for i in items if i['type'] == 'file']
    return {"path": path, "content": folders + files}

@app.get("/api/preview")
def get_preview(repo_id: str, file_path: str, background_tasks: BackgroundTasks, paper_size: str = "a4", orientation: str="portrait", margins: str="default", scale: str="fit", pages: str="all", x_token: str=Header(...)):
    try:
        headers = {"Authorization": f"Token {x_token}"}
        download_url = requests.get(f"{SERVER_URL}/api2/repos/{repo_id}/file/?p={file_path}", headers=headers).text.strip('"')
        
        # Конвертация -> Обрезка -> Отдача
        pdf_path = OnlyOfficeService.convert(download_url, file_path, orientation, margins, scale, paper_size, DOWNLOADS_DIR)
        cropped_path = os.path.join(DOWNLOADS_DIR, f"crop_{uuid.uuid4().hex}.pdf")
        final_pdf = PDFService.extract_pages(pdf_path, pages, cropped_path)
        
        background_tasks.add_task(cleanup_temp_files, pdf_path, cropped_path)
        mime_type, _ = mimetypes.guess_type(final_pdf)
        return FileResponse(final_pdf, media_type=mime_type or "application/octet-stream")
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Ошибка предпросмотра")

@app.post("/api/print")
def print_document(req: PrintRequest, background_tasks: BackgroundTasks, x_token: str = Header(...)):
    try:
        download_url = requests.get(f"{SERVER_URL}/api2/repos/{req.repo_id}/file/?p={req.file_path}", headers={"Authorization": f"Token {x_token}"}).text.strip('"')
        pdf_path = OnlyOfficeService.convert(download_url, req.file_path, req.orientation, req.margins, req.scale, req.paper_size, DOWNLOADS_DIR)

        import subprocess
        cmd = ["lp", "-d", req.printer_name, "-n", str(req.copies), "-o", f"media={req.paper_size.upper()}"]
        
        if req.pages and req.pages.lower() not in ["all", "все", ""]:
            safe_pages = "".join(c for c in req.pages if c.isdigit() or c in "-,")
            if safe_pages: cmd.extend(["-P", safe_pages])
                
        cmd.extend(["-o", f"sides={req.duplex}"]) if req.duplex != "none" else cmd.extend(["-o", "sides=one-sided"])
        cmd.append(pdf_path)

        # Выполняем команду печати
        try:
            subprocess.run(cmd, check=True)
            return {"status": "ok", "message": "Документ успешно отправлен в очередь печати"}
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка системы печати CUPS: {e}")
            raise HTTPException(status_code=500, detail="Ошибка отправки на принтер")
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Ошибка печати")

@app.get("/api/printers")
def get_printers():
    try:
        # Используем lpstat -v, он показывает URI устройств (чтобы найти USB)
        result = subprocess.run(["lpstat", "-v"], capture_output=True, text=True, check=True)
        printers = []
        for line in result.stdout.split('\n'):
            if line.startswith("device for "):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    name_part = parts[0].replace("device for ", "").strip()
                    uri_part = parts[1].strip()
                    
                    # ИГНОРИРУЕМ USB-ПРИНТЕРЫ
                    if not uri_part.startswith("usb://"):
                        printers.append(name_part)
        return {"printers": printers}
    except Exception as e:
        logger.error(f"Ошибка получения списка принтеров: {e}")
        return {"printers": []}

@app.get("/api/printer/{printer_name}/status")
def get_printer_status(printer_name: str):
    try:
        # 1. Узнаем адрес (URI) принтера
        res_v = subprocess.run(["lpstat", "-v", printer_name], capture_output=True, text=True)
        uri = ""
        if res_v.stdout and "device for" in res_v.stdout:
            uri = res_v.stdout.split(":", 1)[1].strip()
        
        # 2. ЖЕСТКИЙ ПИНГ: Если это сетевой принтер, достаем IP и пингуем
        if uri.startswith(("socket://", "lpd://", "ipp://", "http://", "https://")):
            match = re.search(r'://([^/:]+)', uri)
            if match:
                host = match.group(1)
                # Пингуем: 1 пакет, таймаут 1 секунда
                ping_res = subprocess.run(["ping", "-c", "1", "-W", "1", host], capture_output=True)
                if ping_res.returncode != 0:
                    return {"status": "error", "message": "🔴 Принтер отключен от сети"}

        # 3. Если пинг прошел, смотрим статус в CUPS
        result = subprocess.run(["lpstat", "-p", printer_name], capture_output=True, text=True)
        output = result.stdout.lower()
        
        if "disabled" in output or "not connected" in output or "unplugged" in output:
            return {"status": "error", "message": "🔴 Принтер выключен или недоступен"}
        elif "printing" in output:
            return {"status": "ok", "message": "🟡 Печатает другой документ..."}
        elif "idle" in output:
            return {"status": "ok", "message": "🟢 Готов к печати"}
        else:
            return {"status": "unknown", "message": "⚪ Статус неизвестен"}
    except Exception as e:
        logger.error(f"Ошибка проверки статуса принтера: {e}")
        return {"status": "error", "message": "🔴 Ошибка связи с сервером печати"}

@app.on_event("startup")
@repeat_every(seconds=3600) # Нужно установить pip install fastapi-utils
def remove_old_temp_files():
    now = time.time()
    for f in os.listdir(DOWNLOADS_DIR):
        path = os.path.join(DOWNLOADS_DIR, f)
        if os.stat(path).st_mtime < now - 3600:
            try: os.remove(path)
            except: pass