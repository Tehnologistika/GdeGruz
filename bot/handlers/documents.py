from aiogram import Router, F, Bot
from aiogram.types import Message, PhotoSize
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from datetime import datetime
from pathlib import Path
import os
import logging

import db_documents
from db import get_phone

router = Router()
logger = logging.getLogger(__name__)

DOCUMENTS_GROUP_ID = int(os.getenv("DOCUMENTS_GROUP_ID", "0"))
DOCUMENTS_PATH = Path("/home/git/fleet-live-bot/userdata/documents")


class DocumentUpload(StatesGroup):
    """FSM состояния для загрузки документов."""
    waiting_for_type = State()  # Ожидание выбора типа документа
    waiting_for_file = State()  # Ожидание загрузки файла


# Маппинг отображаемых названий на внутренние типы документов
DOC_TYPE_MAPPING = {
    "📸 Фото погрузки": "loading_photo",
    "📸 Фото выгрузки": "unloading_photo",
    "📄 ТТН (товарно-транспортная накладная)": "ttn",
    "📄 Товарная накладная": "invoice",
    "📄 Акт приёма-передачи": "acceptance_act"
}


def document_type_kb():
    """Клавиатура для выбора типа документа."""
    kb = ReplyKeyboardBuilder()
    kb.button(text="📸 Фото погрузки")
    kb.button(text="📸 Фото выгрузки")
    kb.button(text="📄 ТТН (товарно-транспортная накладная)")
    kb.button(text="📄 Товарная накладная")
    kb.button(text="📄 Акт приёма-передачи")
    kb.button(text="❌ Отмена")
    kb.adjust(2, 2, 1, 1)  # 2 кнопки в первых двух рядах, потом по 1
    return kb.as_markup(resize_keyboard=True)


@router.message(F.text == "📤 Отправить документы")
async def start_document_upload(message: Message, state: FSMContext):
    """Начало процесса загрузки документа."""
    await state.set_state(DocumentUpload.waiting_for_type)
    await message.answer(
        "Выберите тип документа:",
        reply_markup=document_type_kb()
    )


@router.message(DocumentUpload.waiting_for_type)
async def process_document_type(message: Message, state: FSMContext):
    """Обработка выбора типа документа."""

    # Проверка на отмену
    if message.text == "❌ Отмена":
        await state.clear()
        from bot.keyboards import location_kb
        await message.answer("Отменено", reply_markup=location_kb())
        return

    # Получение типа документа из маппинга
    doc_type = DOC_TYPE_MAPPING.get(message.text)
    if not doc_type:
        await message.answer("Пожалуйста, выберите тип из кнопок")
        return

    # Сохранение выбранного типа в состояние
    await state.update_data(doc_type=doc_type, type_display=message.text)
    await state.set_state(DocumentUpload.waiting_for_file)

    await message.answer(
        f"Отлично! Теперь отправьте фото: {message.text}\n\n"
        "Можете отправить несколько фотографий подряд."
    )


@router.message(DocumentUpload.waiting_for_file, F.photo)
async def process_document_photo(message: Message, state: FSMContext, bot: Bot):
    """Обработка загруженного фото документа."""

    user_id = message.from_user.id
    data = await state.get_data()
    doc_type = data['doc_type']
    type_display = data['type_display']

    # Получаем фото максимального качества (последнее в списке)
    photo: PhotoSize = message.photo[-1]
    file_id = photo.file_id

    # Скачиваем файл
    file = await bot.get_file(file_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Создаем папку для пользователя
    user_folder = DOCUMENTS_PATH / str(user_id)
    user_folder.mkdir(parents=True, exist_ok=True)

    # Сохраняем файл
    file_extension = file.file_path.split('.')[-1] if '.' in file.file_path else 'jpg'
    file_path = user_folder / f"{doc_type}_{timestamp}.{file_extension}"
    await bot.download_file(file.file_path, file_path)

    # Получаем телефон водителя и активный рейс
    phone = await get_phone(user_id)
    trip_id = await db_documents.get_active_trip(user_id)

    # Сохраняем в БД
    doc_id = await db_documents.save_document(
        user_id=user_id,
        trip_id=trip_id,
        doc_type=doc_type,
        file_id=file_id,
        file_path=str(file_path)
    )

    # Отправляем в группу документов с метаданными
    if DOCUMENTS_GROUP_ID:
        caption = (
            f"📎 **{type_display}**\n"
            f"👤 Водитель: {phone or user_id}\n"
            f"🆔 Рейс: #{trip_id if trip_id else 'не назначен'}\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"📋 ID документа: {doc_id}"
        )
        try:
            await bot.send_photo(
                DOCUMENTS_GROUP_ID,
                photo=file_id,
                caption=caption,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить в группу документов: {e}")

    await message.answer(
        f"✅ {type_display} сохранён!\n\n"
        "Отправьте ещё фото или нажмите /done для завершения"
    )


@router.message(F.text == "/done")
@router.message(F.text == "✅ Завершить")
async def finish_document_upload(message: Message, state: FSMContext):
    """Завершение загрузки документов."""
    current_state = await state.get_state()

    # Очищаем состояние только если мы в процессе загрузки документов
    if current_state and current_state.startswith("DocumentUpload"):
        await state.clear()
        from bot.keyboards import location_kb
        await message.answer(
            "✅ Отлично! Все документы сохранены.",
            reply_markup=location_kb()
        )
    else:
        await message.answer("Нет активной загрузки документов.")
