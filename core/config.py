import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SERVER_URL = os.getenv("SERVER_URL", "https://лис.лицей22.рф")
    ONLYOFFICE_URL = os.getenv("ONLYOFFICE_URL")
    ONLYOFFICE_JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET")
    SEAFILE_ADMIN_TOKEN = os.getenv("SEAFILE_ADMIN_TOKEN")
    
    DOWNLOADS_DIR = "temp_downloads"

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs("static", exist_ok=True)

settings = Settings()