"""
REST API для управления рейсами.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

import db_trips
import db_documents
from web.api import verify_token
from db import get_last_point

router = APIRouter(prefix="/api/trips", tags=["trips"])


class TripCreate(BaseModel):
    """Модель для создания рейса."""
    trip_number: str = Field(..., description="Уникальный номер рейса")
    user_id: int = Field(..., description="Telegram ID водителя")
    customer: str = Field(..., description="Заказчик")
    carrier: str = Field(..., description="Перевозчик")
    loading_address: str = Field(..., description="Адрес погрузки")
    loading_date: str = Field(..., description="Дата погрузки (ISO формат)")
    unloading_address: str = Field(..., description="Адрес выгрузки")
    unloading_date: str = Field(..., description="Дата выгрузки (ISO формат)")
    cargo_type: str = Field(..., description="Тип груза")
    rate: float = Field(..., description="Ставка в рублях")
    curator_id: Optional[int] = Field(None, description="ID куратора")


class TripUpdate(BaseModel):
    """Модель для обновления рейса."""
    status: Optional[str] = Field(None, description="Новый статус")
    loading_lat: Optional[float] = Field(None, description="Широта погрузки")
    loading_lon: Optional[float] = Field(None, description="Долгота погрузки")
    unloading_lat: Optional[float] = Field(None, description="Широта выгрузки")
    unloading_lon: Optional[float] = Field(None, description="Долгота выгрузки")
    documents_sent: Optional[str] = Field(None, description="Трек-номер СДЭК")


class EventCreate(BaseModel):
    """Модель для создания события."""
    event_type: str = Field(..., description="Тип события")
    description: str = Field(..., description="Описание события")
    created_by: Optional[int] = Field(None, description="ID создателя")


@router.post("/create", status_code=201)
async def create_trip(trip: TripCreate, _: bool = Depends(verify_token)):
    """
    Создать новый рейс.

    Требует авторизации.
    """
    try:
        trip_id = await db_trips.create_trip(**trip.dict())
        return {
            "trip_id": trip_id,
            "trip_number": trip.trip_number,
            "status": "created"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{trip_id}")
async def get_trip(trip_id: int, _: bool = Depends(verify_token)):
    """
    Получить информацию о рейсе.

    Требует авторизации.
    """
    trip = await db_trips.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/number/{trip_number}")
async def get_trip_by_number(trip_number: str, _: bool = Depends(verify_token)):
    """
    Получить информацию о рейсе по номеру.

    Требует авторизации.
    """
    trip = await db_trips.get_trip_by_number(trip_number)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.put("/{trip_id}")
async def update_trip(
    trip_id: int,
    updates: TripUpdate,
    _: bool = Depends(verify_token)
):
    """
    Обновить рейс.

    Требует авторизации.
    """
    # Проверяем существование рейса
    trip = await db_trips.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Обновляем статус если указан
    if updates.status:
        await db_trips.update_trip_status(trip_id, updates.status)

    # Обновляем трек-номер если указан
    if updates.documents_sent:
        await db_trips.update_trip_documents_tracking(
            trip_id,
            tracking_number=updates.documents_sent
        )

    return {"status": "updated", "trip_id": trip_id}


@router.get("/{trip_id}/documents")
async def get_trip_documents(trip_id: int, _: bool = Depends(verify_token)):
    """
    Получить все документы по рейсу.

    Требует авторизации.
    """
    docs = await db_documents.get_trip_documents(trip_id)
    return {"trip_id": trip_id, "documents": docs}


@router.get("/{trip_id}/events")
async def get_trip_events(trip_id: int, _: bool = Depends(verify_token)):
    """
    Получить историю событий рейса.

    Требует авторизации.
    """
    events = await db_trips.get_trip_events(trip_id)
    return {"trip_id": trip_id, "events": events}


@router.post("/{trip_id}/events", status_code=201)
async def add_trip_event(
    trip_id: int,
    event: EventCreate,
    _: bool = Depends(verify_token)
):
    """
    Добавить событие к рейсу.

    Требует авторизации.
    """
    # Проверяем существование рейса
    trip = await db_trips.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    event_id = await db_trips.log_trip_event(
        trip_id=trip_id,
        event_type=event.event_type,
        description=event.description,
        created_by=event.created_by
    )

    return {"event_id": event_id, "trip_id": trip_id}


@router.get("/")
async def list_active_trips(
    user_id: Optional[int] = Query(None, description="Фильтр по водителю"),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    _: bool = Depends(verify_token)
):
    """
    Получить список активных рейсов.

    Требует авторизации.
    """
    if user_id:
        trips = await db_trips.get_user_active_trips(user_id)
    else:
        trips = await db_trips.get_all_active_trips()

    # Фильтрация по статусу если указан
    if status:
        trips = [t for t in trips if t['status'] == status]

    return {"trips": trips, "count": len(trips)}


@router.get("/{trip_id}/summary")
async def get_trip_summary(trip_id: int, _: bool = Depends(verify_token)):
    """
    Получить полную сводку по рейсу (для дашборда).

    Включает:
    - Информацию о рейсе
    - События
    - Документы
    - Последнее местоположение водителя

    Требует авторизации.
    """
    # Основная информация о рейсе
    trip = await db_trips.get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # События
    events = await db_trips.get_trip_events(trip_id)

    # Документы
    documents = await db_documents.get_trip_documents(trip_id)

    # Последнее местоположение водителя
    last_location = await get_last_point(trip['user_id'])

    return {
        "trip": trip,
        "events": events,
        "documents": documents,
        "last_location": last_location
    }
