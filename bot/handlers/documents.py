"""
Обработчик загрузки документов водителями.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from pathlib import Path
import os
import logging

import db_documents
from db import get_phone

router = Router()
logger = logging.getLogger(__name__)

# Настройки из переменных окружения
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
DOCUMENTS_DIR = Path("/home/user/GdeGruz/userdata/documents")

# Создаем директорию для документов
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


class DocumentUpload(StatesGroup):
    """Состояния FSM для загрузки документов."""
    waiting_for_type = State()
    waiting_for_file = State()


def doc_type_keyboard():
    """Inline-клавиатура выбора типа документа."""
    kb = InlineKeyboardBuilder()

    kb.button(text="📸 Фото погрузки", callback_data="doc:loading_photo")
    kb.button(text="📸 Фото выгрузки", callback_data="doc:unloading_photo")
    kb.button(text="📄 ТТН", callback_data="doc:ttn")
    kb.button(text="📄 УПД", callback_data="doc:upd")
    kb.button(text="📄 Другой документ", callback_data="doc:other")
    kb.button(text="❌ Отмена", callback_data="doc:cancel")

    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


@router.message(Command("documents"))
@router.message(F.text == "📤 Отправить документы")
async def start_document_upload(message: Message, state: FSMContext):
    """Начать загрузку документа."""
    await state.set_state(DocumentUpload.waiting_for_type)

    await message.answer(
        "📤 Выберите тип документа:",
        reply_markup=doc_type_keyboard()
    )


@router.callback_query(F.data.startswith("doc:"))
async def handle_doc_type_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора типа документа."""
    doc_type = callback.data.split(":")[1]

    if doc_type == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Загрузка документа отменена")
        await callback.answer()
        return

    # Сохраняем выбранный тип в состоянии
    await state.update_data(doc_type=doc_type)
    await state.set_state(DocumentUpload.waiting_for_file)

    # Получаем красивое название типа документа
    doc_names = {
        "loading_photo": "📸 Фото погрузки",
        "unloading_photo": "📸 Фото выгрузки",
        "ttn": "📄 ТТН",
        "upd": "📄 УПД",
        "other": "📄 Другой документ"
    }

    doc_name = doc_names.get(doc_type, doc_type)

    await callback.message.edit_text(
        f"Отлично! Теперь отправьте {doc_name}.\n\n"
        "Вы можете отправить фото или документ.\n"
        "Для отмены отправьте /cancel"
    )
    await callback.answer()


@router.message(DocumentUpload.waiting_for_file, F.photo)
async def handle_photo_document(message: Message, state: FSMContext):
    """Обработчик фото-документа."""
    data = await state.get_data()
    doc_type = data.get("doc_type")

    if not doc_type:
        await message.answer("❌ Ошибка: тип документа не выбран. Начните заново с /documents")
        await state.clear()
        return

    # Получаем наилучшее качество фото
    photo = message.photo[-1]
    file_id = photo.file_id

    user_id = message.from_user.id

    try:
        # Сохраняем информацию о документе в БД
        doc_id = await db_documents.save_document(
            user_id=user_id,
            doc_type=doc_type,
            file_id=file_id
        )

        # Отправляем в группу документов если настроена
        telegram_msg_id = None
        if GROUP_CHAT_ID:
            try:
                phone = await get_phone(user_id)

                # Получаем информацию о рейсе если есть
                trip_info = ""
                trip_id = await db_documents.get_active_trip(user_id)
                if trip_id:
                    import db_trips
                    trip = await db_trips.get_trip(trip_id)
                    if trip:
                        trip_info = f"\n🆔 Рейс: #{trip['trip_number']}"

                doc_names = {
                    "loading_photo": "📸 Фото погрузки",
                    "unloading_photo": "📸 Фото выгрузки",
                    "ttn": "📄 ТТН",
                    "upd": "📄 УПД",
                    "other": "📄 Другой документ"
                }

                caption = (
                    f"📎 **{doc_names.get(doc_type, doc_type)}**\n"
                    f"👤 Водитель: {phone or user_id}{trip_info}\n"
                    f"🕐 {message.date.strftime('%d.%m.%Y %H:%M')}\n"
                    f"📋 ID документа: {doc_id}"
                )

                sent_msg = await message.bot.send_photo(
                    GROUP_CHAT_ID,
                    photo=file_id,
                    caption=caption,
                    parse_mode="Markdown"
                )
                telegram_msg_id = sent_msg.message_id

                # Обновляем telegram_msg_id в БД
                # (можно добавить функцию update_document в db_documents.py)

            except Exception as e:
                logger.error(f"Failed to send document to group: {e}")

        await message.answer(
            f"✅ {db_documents.DOC_TYPES.get(doc_type, doc_type)} сохранён!\n"
            f"📋 ID документа: {doc_id}"
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Failed to save document: {e}")
        await message.answer("❌ Ошибка при сохранении документа. Попробуйте еще раз.")


@router.message(DocumentUpload.waiting_for_file, F.document)
async def handle_file_document(message: Message, state: FSMContext):
    """Обработчик файлового документа."""
    data = await state.get_data()
    doc_type = data.get("doc_type")

    if not doc_type:
        await message.answer("❌ Ошибка: тип документа не выбран. Начните заново с /documents")
        await state.clear()
        return

    document = message.document
    file_id = document.file_id

    user_id = message.from_user.id

    try:
        # Сохраняем информацию о документе в БД
        doc_id = await db_documents.save_document(
            user_id=user_id,
            doc_type=doc_type,
            file_id=file_id
        )

        # Отправляем в группу документов если настроена
        if GROUP_CHAT_ID:
            try:
                phone = await get_phone(user_id)

                # Получаем информацию о рейсе если есть
                trip_info = ""
                trip_id = await db_documents.get_active_trip(user_id)
                if trip_id:
                    import db_trips
                    trip = await db_trips.get_trip(trip_id)
                    if trip:
                        trip_info = f"\n🆔 Рейс: #{trip['trip_number']}"

                doc_names = {
                    "loading_photo": "📸 Фото погрузки",
                    "unloading_photo": "📸 Фото выгрузки",
                    "ttn": "📄 ТТН",
                    "upd": "📄 УПД",
                    "other": "📄 Другой документ"
                }

                caption = (
                    f"📎 **{doc_names.get(doc_type, doc_type)}**\n"
                    f"👤 Водитель: {phone or user_id}{trip_info}\n"
                    f"📄 Файл: {document.file_name}\n"
                    f"🕐 {message.date.strftime('%d.%m.%Y %H:%M')}\n"
                    f"📋 ID документа: {doc_id}"
                )

                await message.bot.send_document(
                    GROUP_CHAT_ID,
                    document=file_id,
                    caption=caption,
                    parse_mode="Markdown"
                )

            except Exception as e:
                logger.error(f"Failed to send document to group: {e}")

        await message.answer(
            f"✅ {db_documents.DOC_TYPES.get(doc_type, doc_type)} сохранён!\n"
            f"📋 ID документа: {doc_id}"
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Failed to save document: {e}")
        await message.answer("❌ Ошибка при сохранении документа. Попробуйте еще раз.")


@router.message(DocumentUpload.waiting_for_file, Command("cancel"))
async def cancel_document_upload(message: Message, state: FSMContext):
    """Отмена загрузки документа."""
    await state.clear()
    await message.answer("❌ Загрузка документа отменена")


@router.message(DocumentUpload.waiting_for_file)
async def invalid_document_type(message: Message):
    """Обработчик неверного типа документа."""
    await message.answer(
        "❌ Пожалуйста, отправьте фото или документ.\n"
        "Для отмены отправьте /cancel"
    )


@router.message(Command("my_documents"))
async def show_my_documents(message: Message):
    """Показать мои документы."""
    user_id = message.from_user.id

    try:
        docs = await db_documents.get_user_documents(user_id)

        if not docs:
            await message.answer("У вас пока нет загруженных документов.")
            return

        response = f"📄 Ваши документы ({len(docs)}):\n\n"

        for doc in docs[:10]:  # Показываем последние 10
            doc_type_name = db_documents.DOC_TYPES.get(doc['doc_type'], doc['doc_type'])
            created_at = doc['created_at'][:16].replace('T', ' ')

            trip_info = ""
            if doc.get('trip_id'):
                trip_info = f" | Рейс ID: {doc['trip_id']}"

            response += f"• {doc_type_name} - {created_at}{trip_info}\n"

        if len(docs) > 10:
            response += f"\n... и еще {len(docs) - 10} документов"

        await message.answer(response)

    except Exception as e:
        logger.error(f"Failed to get user documents: {e}")
        await message.answer("❌ Ошибка при получении списка документов")
