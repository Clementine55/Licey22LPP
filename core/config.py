import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SERVER_URL = os.getenv("SERVER_URL", "https://лис.лицей22.рф")
    ONLYOFFICE_URL = os.getenv("ONLYOFFICE_URL")
    ONLYOFFICE_JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET")
    DOWNLOADS_DIR = "temp_downloads"

    # Гарантируем наличие папки при старте
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs("static", exist_ok=True)

settings = Settings()