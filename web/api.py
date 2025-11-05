import os
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from db import get_last_point, init, get_last_points, get_phone
from web.api_trips import router as trips_router

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Подключаем роутер для рейсов
app.include_router(trips_router)

# FIX: Добавляем секретный токен для доступа к API
# Установите API_SECRET_TOKEN в .env файле
API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN", "")

if not API_SECRET_TOKEN:
    import secrets
    # Если токен не установлен, генерируем временный и предупреждаем
    API_SECRET_TOKEN = secrets.token_urlsafe(32)
    print("=" * 70)
    print("⚠️  WARNING: API_SECRET_TOKEN не установлен в .env!")
    print(f"⚠️  Используется временный токен: {API_SECRET_TOKEN}")
    print("⚠️  Добавьте в .env файл:")
    print(f"API_SECRET_TOKEN={API_SECRET_TOKEN}")
    print("=" * 70)


def verify_token(authorization: Optional[str] = Header(None)) -> bool:
    """
    Проверяет токен авторизации.
    Формат: Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация. Добавьте заголовок: Authorization: Bearer <token>"
        )
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Неверный формат токена. Используйте: Authorization: Bearer <token>"
        )
    
    if token != API_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Неверный токен")
    
    return True


@app.on_event("startup")
async def startup() -> None:
    await init()


templates = Jinja2Templates(directory="templates")


@app.get("/healthz")
async def healthz():
    """Simple health check endpoint (без авторизации)."""
    return {"status": "ok"}


@app.get("/api/last/{user_id}")
async def api_last(user_id: int, _: bool = Depends(verify_token)):
    """
    Возвращает последнее местоположение водителя.
    
    ТРЕБУЕТ АВТОРИЗАЦИИ!
    Добавьте заголовок: Authorization: Bearer <ваш_токен>
    """
    point = await get_last_point(user_id)
    if not point:
        raise HTTPException(status_code=404, detail="Point not found")
    return {
        "lat": point["lat"],
        "lon": point["lon"],
        "ts": point["ts"].isoformat(),
    }


@app.get("/map/{user_id}", response_class=HTMLResponse)
async def map_view(
    request: Request, 
    user_id: int,
    token: Optional[str] = None
):
    """
    Отображает карту с местоположением водителя.
    
    Использование:
    /map/{user_id}?token=<ваш_токен>
    """
    # Проверка токена через query parameter для удобства
    if token != API_SECRET_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещен. Используйте: /map/{user_id}?token=<ваш_токен>"
        )
    
    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "user_id": user_id,
            "api_token": API_SECRET_TOKEN,  # Передаем токен в шаблон
        },
    )


@app.get("/api/drivers")
async def list_drivers(_: bool = Depends(verify_token)):
    """
    Возвращает список всех активных водителей с последними координатами.
    """
    points_list = await get_last_points()
    
    result = []
    for user_id, last_ts in points_list:
        phone = await get_phone(user_id)
        result.append({
            "user_id": user_id,
            "phone": phone,
            "last_update": last_ts.isoformat(),
        })
    
    return {"drivers": result}