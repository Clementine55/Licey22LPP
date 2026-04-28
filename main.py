from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import os
import time
import logging
from contextlib import asynccontextmanager

from core.config import settings
from api import routes_auth, routes_files, routes_print

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s')

# Фоновая задача очистки мусора
async def cleanup_background_task():
    while True:
        try:
            now = time.time()
            for f in os.listdir(settings.DOWNLOADS_DIR):
                path = os.path.join(settings.DOWNLOADS_DIR, f)
                if os.stat(path).st_mtime < now - 3600:
                    try: os.remove(path)
                    except: pass
        except Exception:
            pass
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_background_task())
    yield
    task.cancel()

# Инициализация приложения
app = FastAPI(title="Единый портал печати Лицея", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключение модулей (маршрутизаторов)
app.include_router(routes_auth.router, prefix="/api")
app.include_router(routes_files.router, prefix="/api")
app.include_router(routes_print.router, prefix="/api")

# Отдача фронтенда
@app.get("/")
def serve_frontend(): 
    return FileResponse("static/index.html")