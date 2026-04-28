from fastapi import APIRouter, Header
from schemas.print_models import LoginData

router = APIRouter(tags=["Авторизация"])

@router.post("/login")
def login(data: LoginData):
    # Фейковая функция. Мы возвращаем заглушку, чтобы старый JS-код
    # на фронтенде думал, что он вошел, пока мы не перепишем сам фронтенд.
    return {"token": "sso-bypass-token"}

@router.get("/user")
def get_user_info(
    username: str = Header("Пользователь", alias="X-Authentik-Username"),
    email: str = Header("", alias="X-Authentik-Email")
):
    # Берем имя прямо из заголовка от SSO сервера
    return {"name": username, "avatar_url": ""}