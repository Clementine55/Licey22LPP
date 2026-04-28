from fastapi import APIRouter, HTTPException, Header
import requests
from core.config import settings
from schemas.print_models import LoginData

router = APIRouter(tags=["Авторизация"])

@router.post("/login")
def login(data: LoginData):
    resp = requests.post(f"{settings.SERVER_URL}/api2/auth-token/", data={"username": data.username, "password": data.password})
    if resp.status_code == 200: 
        return {"token": resp.json().get('token')}
    raise HTTPException(status_code=401, detail="Неверный логин или пароль")

@router.get("/user")
def get_user_info(x_token: str = Header(...)):
    try:
        resp = requests.get(f"{settings.SERVER_URL}/api2/account/info/", headers={"Authorization": f"Token {x_token}"})
        data = resp.json()
        avatar = data.get("avatar_url", "")
        if avatar.startswith("/"): 
            avatar = settings.SERVER_URL + avatar
        return {"name": data.get("name", data.get("email", "Пользователь")), "avatar_url": avatar}
    except Exception:
        return {"name": "Пользователь", "avatar_url": ""}