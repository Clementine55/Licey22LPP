from fastapi import APIRouter, Header, Depends
import httpx
from core.config import settings
from schemas.print_models import LoginData
import logging

logger = logging.getLogger("PrintPortal")
router = APIRouter(tags=["Авторизация"])

ADMIN_HEADERS = {"Authorization": f"Token {settings.SEAFILE_ADMIN_TOKEN}"}

async def get_real_seafile_token(username: str = Header(..., alias="X-Authentik-Username")):
    seafile_user = f"{username}@licey22.local"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.SERVER_URL}/api/v2.1/admin/generate-user-auth-token/",
            data={"email": seafile_user},
            headers=ADMIN_HEADERS
        )
        if resp.status_code == 200:
            return resp.json().get("token")
    return None

@router.post("/login")
async def login(data: LoginData):
    return {"token": "sso-bypass-token"}

@router.get("/user")
async def get_user_info(real_token: str = Depends(get_real_seafile_token)):
    if not real_token:
        return {"name": "Вход через SSO", "avatar_url": ""}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.SERVER_URL}/api2/account/info/", 
                headers={"Authorization": f"Token {real_token}"}
            )
            data = resp.json()
            avatar = data.get("avatar_url", "")
            if avatar.startswith("/"): 
                avatar = settings.SERVER_URL + avatar
            return {"name": data.get("name", data.get("email", "Пользователь")), "avatar_url": avatar}
    except Exception:
        return {"name": "Пользователь", "avatar_url": ""}