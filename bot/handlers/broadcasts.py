import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, desc, and_
from ..models.base import async_session
from ..models.models import User, Broadcast, BroadcastRecipient
from ..states.states import BroadcastForm
import os
import asyncio
import re

router = Router()

# Админский ID из переменных окружения
ADMIN_ID = int(os.getenv("ADMIN_ID", "5385155120"))

# Функция проверки на админа
def is_admin(telegram_id):
    return telegram_id == ADMIN_ID

# Получить клавиатуру меню рассылок
def get_broadcasts_menu_kb():
    kb = [
        [InlineKeyboardButton(text="📝 Создать рассылку", callback_data="create_broadcast")],
        [InlineKeyboardButton(text="📊 Активные рассылки", callback_data="active_broadcasts")],
        [InlineKeyboardButton(text="📈 История рассылок", callback_data="broadcast_history")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.callback_query(F.data == "admin_broadcasts")
async def admin_broadcasts_menu(callback: CallbackQuery):
    """Меню рассылок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return

    async with async_session() as session:
        # Получаем статистику по рассылкам
        total_broadcasts = await session.scalar(select(func.count()).select_from(Broadcast))
        active_broadcasts = await session.scalar(
            select(func.count()).select_from(Broadcast).where(
                Broadcast.status.in_(["created", "sending"])
            )
        )
        scheduled_broadcasts = await session.scalar(
            select(func.count()).select_from(Broadcast).where(
                and_(
                    Broadcast.status == "created",
                    Broadcast.scheduled_at.isnot(None)
                )
            )
        )
        
        # Получаем последние рассылки
        recent_broadcasts_query = select(Broadcast).order_by(desc(Broadcast.created_at)).limit(3)
        result = await session.execute(recent_broadcasts_query)
        recent_broadcasts = result.scalars().all()
        
        text = (
            "📨 Рассылки сообщений\n\n"
            f"Всего рассылок: {total_broadcasts}\n"
            f"Активных рассылок: {active_broadcasts}\n"
            f"Запланированных: {scheduled_broadcasts}\n\n"
        )
        
        if recent_broadcasts:
            text += "Последние рассылки:\n"
            for i, broadcast in enumerate(recent_broadcasts, 1):
                status_emoji = {
                    "created": "⏳",
                    "sending": "🔄",
                    "completed": "✅",
                    "failed": "❌"
                }.get(broadcast.status, "❓")
                
                # Форматируем информацию о рассылке
                text += (
                    f"{i}. {status_emoji} {broadcast.name}\n"
                    f"   Статус: {broadcast.status}\n"
                    f"   Создана: {broadcast.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                )
                
                if broadcast.scheduled_at:
                    text += f"   Запланирована на: {broadcast.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
                    
                if broadcast.sent_at:
                    text += f"   Отправлена: {broadcast.sent_at.strftime('%d.%m.%Y %H:%M')}\n"
                    
                if broadcast.status in ["completed", "sending"]:                        
                    text += (
                        f"   Получили: {broadcast.received_count}/{broadcast.total_users}\n"
                    )
                
                text += "\n"
        else:
            text += "Пока нет рассылок\n"
        
        try:
            await callback.message.edit_text(text, reply_markup=get_broadcasts_menu_kb())
        except Exception as e:
            logging.error(f"Error editing message in admin_broadcasts_menu: {e}")
            await callback.message.answer(text, reply_markup=get_broadcasts_menu_kb())
            
        await callback.answer()

@router.callback_query(F.data == "create_broadcast")
async def create_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Устанавливаем состояние для имени рассылки
    await state.set_state(BroadcastForm.waiting_for_name)
    
    try:
        await callback.message.edit_text(
            "📝 Создание новой рассылки\n\n"
            "Введите название рассылки (только для вас, для идентификации):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
            ])
        )
    except Exception as e:
        logging.error(f"Error editing message in create_broadcast_start: {e}")
        await callback.message.answer(
            "📝 Создание новой рассылки\n\n"
            "Введите название рассылки (только для вас, для идентификации):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
            ])
        )
    
    await callback.answer() 

@router.message(BroadcastForm.waiting_for_name)
async def process_broadcast_name(message: Message, state: FSMContext):
    """Обработка ввода названия рассылки"""
    if not is_admin(message.from_user.id):
        return
    
    broadcast_name = message.text.strip()
    
    if not broadcast_name:
        await message.answer("Название не может быть пустым. Пожалуйста, введите название рассылки:")
        return
    
    # Сохраняем название в состоянии
    await state.update_data(name=broadcast_name)
    
    # Переходим к следующему шагу - вводу текста сообщения
    await state.set_state(BroadcastForm.waiting_for_text)
    
    await message.answer(
        "📝 Введите текст сообщения для рассылки:\n\n"
        "Вы можете использовать HTML-разметку:\n"
        "- <b>Жирный текст</b>\n"
        "- <i>Курсив</i>\n"
        "- <u>Подчеркнутый</u>\n"
        "- <a href='https://example.com'>Ссылка</a>\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
        ])
    )

@router.message(BroadcastForm.waiting_for_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    """Обработка ввода текста рассылки"""
    if not is_admin(message.from_user.id):
        return
    
    broadcast_text = message.text.strip()
    
    if not broadcast_text:
        await message.answer("Текст сообщения не может быть пустым. Пожалуйста, введите текст:")
        return
    
    # Сохраняем текст в состоянии
    await state.update_data(text=broadcast_text)
    
    # Переходим к следующему шагу - выбору добавления фото
    await state.set_state(BroadcastForm.waiting_for_photo)
    
    await message.answer(
        "🖼 Хотите добавить изображение к рассылке?\n\n"
        "Отправьте фото или выберите одну из опций ниже:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_broadcast_photo")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
        ])
    )

@router.message(BroadcastForm.waiting_for_photo, F.photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    """Обработка фото для рассылки"""
    if not is_admin(message.from_user.id):
        return
    
    # Получаем file_id самого большого размера фото
    photo_id = message.photo[-1].file_id
    
    # Сохраняем ID фото в состоянии
    await state.update_data(photo=photo_id)
    
    # Переходим к выбору добавления кнопки
    await state.set_state(BroadcastForm.waiting_for_button)
    
    await message.answer(
        "🔘 Хотите добавить кнопку со ссылкой?\n\n"
        "Это поможет отслеживать конверсию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, добавить кнопку", callback_data="add_broadcast_button")],
            [InlineKeyboardButton(text="➡️ Нет, пропустить", callback_data="skip_broadcast_button")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
        ])
    )

@router.callback_query(F.data == "skip_broadcast_photo")
async def skip_broadcast_photo(callback: CallbackQuery, state: FSMContext):
    """Пропуск добавления фото к рассылке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Сохраняем отсутствие фото
    await state.update_data(photo=None)
    
    # Переходим к выбору добавления кнопки
    await state.set_state(BroadcastForm.waiting_for_button)
    
    await callback.message.edit_text(
        "🔘 Хотите добавить кнопку со ссылкой?\n\n"
        "Это поможет отслеживать конверсию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, добавить кнопку", callback_data="add_broadcast_button")],
            [InlineKeyboardButton(text="➡️ Нет, пропустить", callback_data="skip_broadcast_button")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
        ])
    )
    
    await callback.answer()

@router.callback_query(F.data == "add_broadcast_button")
async def add_broadcast_button(callback: CallbackQuery, state: FSMContext):
    """Добавление кнопки к рассылке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Переходим к вводу текста кнопки
    await state.set_state(BroadcastForm.waiting_for_button_text)
    
    await callback.message.edit_text(
        "✏️ Введите текст для кнопки:\n\n"
        "Например: 'Подробнее', 'Перейти' и т.д.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
        ])
    )
    
    await callback.answer()

@router.message(BroadcastForm.waiting_for_button_text)
async def process_button_text(message: Message, state: FSMContext):
    """Обработка текста кнопки"""
    if not is_admin(message.from_user.id):
        return
    
    button_text = message.text.strip()
    
    if not button_text:
        await message.answer("Текст кнопки не может быть пустым. Пожалуйста, введите текст:")
        return
    
    # Сохраняем текст кнопки
    await state.update_data(button_text=button_text)
    
    # Переходим к вводу URL для кнопки
    await state.set_state(BroadcastForm.waiting_for_button_url)
    
    await message.answer(
        "🔗 Введите URL для кнопки:\n\n"
        "URL должен начинаться с http:// или https://",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
        ])
    )

@router.message(BroadcastForm.waiting_for_button_url)
async def process_button_url(message: Message, state: FSMContext):
    """Обработка URL кнопки"""
    if not is_admin(message.from_user.id):
        return
    
    button_url = message.text.strip()
    
    # Проверяем корректность URL
    if not button_url.startswith(('http://', 'https://')):
        await message.answer(
            "❌ Некорректный URL. URL должен начинаться с http:// или https://\n\n"
            "Пожалуйста, введите корректный URL:"
        )
        return
    
    # Сохраняем URL кнопки
    await state.update_data(button_url=button_url)
    
    # Переходим к подтверждению рассылки
    await show_broadcast_preview(message, state)

@router.callback_query(F.data == "skip_broadcast_button")
async def skip_broadcast_button(callback: CallbackQuery, state: FSMContext):
    """Пропуск добавления кнопки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Сохраняем отсутствие кнопки
    await state.update_data(button_text=None, button_url=None)
    
    # Переходим к подтверждению рассылки
    await show_broadcast_preview(callback.message, state)
    
    await callback.answer()

async def show_broadcast_preview(message: Message, state: FSMContext):
    """Показывает предпросмотр рассылки и запрашивает подтверждение"""
    # Получаем данные о рассылке
    data = await state.get_data()
    
    name = data.get("name", "Без названия")
    text = data.get("text", "Текст отсутствует")
    photo = data.get("photo")
    button_text = data.get("button_text")
    button_url = data.get("button_url")
    
    # Отдельное сообщение с примером текста рассылки с форматированием HTML
    # Отправляем сначала, чтобы это сообщение было первым
    await message.answer(
        f"📱 Так будет выглядеть текст рассылки:\n\n{text}",
        parse_mode="HTML"
    )
    
    # Создаем текст предпросмотра
    preview_text = (
        "📋 Предпросмотр рассылки\n\n"
        f"📝 Название: {name}\n"
        f"📱 Текст сообщения:\n\n{text}\n\n"
    )
    
    if photo:
        preview_text += "🖼 Фото: Прикреплено\n"
    else:
        preview_text += "🖼 Фото: Отсутствует\n"
    
    if button_text and button_url:
        preview_text += f"🔘 Кнопка: {button_text} ({button_url})\n"
    else:
        preview_text += "🔘 Кнопка: Отсутствует\n"
    
    # Подсчитываем количество получателей
    async with async_session() as session:
        total_users = await session.scalar(select(func.count()).select_from(User))
        preview_text += f"\nПолучателей: {total_users} пользователей\n\n"
    
    # Создаем клавиатуру для подтверждения или редактирования
    kb = [
        [
            InlineKeyboardButton(text="✅ Отправить сейчас", callback_data="send_broadcast_now"),
            InlineKeyboardButton(text="⏰ Запланировать", callback_data="schedule_broadcast")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
    ]
    
    # Переходим к состоянию ожидания подтверждения
    await state.set_state(BroadcastForm.waiting_for_confirmation)
    
    # Отправляем сообщение с кнопкой для подтверждения
    # Запоминаем ID сообщения для использования в колбэках
    preview_message = None
    if photo:
        try:
            preview_message = await message.answer_photo(
                photo,
                caption=preview_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            )
        except Exception as e:
            logging.error(f"Error sending photo preview: {e}")
            preview_message = await message.answer(
                preview_text + "\n⚠️ Ошибка при отображении фото",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            )
    else:
        preview_message = await message.answer(
            preview_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    
    # Сохраняем ID сообщения с превью в состоянии
    if preview_message:
        await state.update_data(preview_message_id=preview_message.message_id)

@router.callback_query(F.data == "send_broadcast_now")
async def send_broadcast_now(callback: CallbackQuery, state: FSMContext):
    """Моментальная отправка рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Получаем данные о рассылке
    data = await state.get_data()
    
    # Создаем запись в базе данных
    async with async_session() as session:
        # Подсчитываем общее количество пользователей
        total_users = await session.scalar(select(func.count()).select_from(User))
        
        # Создаем новую рассылку
        new_broadcast = Broadcast(
            name=data.get("name"),
            text=data.get("text"),
            photo=data.get("photo"),
            button_text=data.get("button_text"),
            button_url=data.get("button_url"),
            status="sending",
            total_users=total_users
        )
        
        session.add(new_broadcast)
        await session.commit()
        
        # Запускаем процесс рассылки
        asyncio.create_task(
            send_broadcast(
                callback.bot, 
                new_broadcast.id, 
                callback.from_user.id
            )
        )
    
    # Очищаем состояние
    await state.clear()
    
    # Сообщение об успешном запуске рассылки
    success_text = (
        "✅ Рассылка запущена!\n\n"
        "Процесс рассылки выполняется в фоновом режиме.\n"
        "Результаты будут доступны в разделе 'Активные рассылки'."
    )
    
    success_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Активные рассылки", callback_data="active_broadcasts")],
        [InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")]
    ])
    
    # Отправляем новое сообщение вместо редактирования старого
    await callback.message.answer(success_text, reply_markup=success_kb)
    
    # Отвечаем на колбэк, чтобы убрать часы загрузки
    await callback.answer()

@router.callback_query(F.data == "schedule_broadcast")
async def schedule_broadcast_date(callback: CallbackQuery, state: FSMContext):
    """Планирование рассылки - выбор даты"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Устанавливаем состояние для выбора даты
    await state.set_state(BroadcastForm.waiting_for_schedule_date)
    
    try:
        await callback.message.edit_text(
            "📅 Планирование рассылки\n\n"
            "Введите дату в формате ДД.ММ.ГГГГ\n"
            "Например: 25.12.2025",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
            ])
        )
    except Exception as e:
        logging.error(f"Error editing message in schedule_broadcast_date: {e}")
        # Если не удалось отредактировать сообщение, отправляем новое
        await callback.message.answer(
            "📅 Планирование рассылки\n\n"
            "Введите дату в формате ДД.ММ.ГГГГ\n"
            "Например: 25.12.2025",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
            ])
        )
    
    await callback.answer()

@router.message(BroadcastForm.waiting_for_schedule_date)
async def process_schedule_date(message: Message, state: FSMContext):
    """Обработка даты планирования"""
    if not is_admin(message.from_user.id):
        return
    
    date_str = message.text.strip()
    
    # Проверяем формат даты
    date_pattern = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
    
    if not date_pattern.match(date_str):
        await message.answer(
            "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ\n"
            "Например: 25.12.2025\n\n"
            "Попробуйте еще раз:"
        )
        return
    
    try:
        day, month, year = map(int, date_str.split('.'))
        schedule_date = datetime(year, month, day)
        
        # Проверяем, что дата не в прошлом
        if schedule_date.date() < datetime.now().date():
            await message.answer(
                "❌ Нельзя запланировать рассылку на прошедшую дату.\n"
                "Пожалуйста, выберите дату начиная с сегодняшнего дня:"
            )
            return
        
        # Сохраняем дату в состоянии
        await state.update_data(schedule_date=schedule_date)
        
        # Переходим к выбору времени
        await state.set_state(BroadcastForm.waiting_for_schedule_time)
        
        await message.answer(
            "🕒 Теперь введите время в формате ЧЧ:ММ\n"
            "Например: 14:30",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcasts")]
            ])
        )
    
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты или невозможная дата.\n"
            "Пожалуйста, используйте формат ДД.ММ.ГГГГ и убедитесь,\n"
            "что дата существует в календаре.\n\n"
            "Попробуйте еще раз:"
        )

@router.message(BroadcastForm.waiting_for_schedule_time)
async def process_schedule_time(message: Message, state: FSMContext):
    """Обработка времени планирования"""
    if not is_admin(message.from_user.id):
        return
    
    time_str = message.text.strip()
    
    # Проверяем формат времени
    time_pattern = re.compile(r"^\d{1,2}:\d{2}$")
    
    if not time_pattern.match(time_str):
        await message.answer(
            "❌ Неверный формат времени. Используйте формат ЧЧ:ММ\n"
            "Например: 14:30\n\n"
            "Попробуйте еще раз:"
        )
        return
    
    try:
        hour, minute = map(int, time_str.split(':'))
        
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Invalid time values")
        
        # Получаем дату из состояния
        data = await state.get_data()
        schedule_date = data.get("schedule_date")
        
        # Обновляем дату с учетом времени
        schedule_datetime = schedule_date.replace(hour=hour, minute=minute)
        
        # Проверяем, что время не в прошлом
        if schedule_datetime < datetime.now():
            await message.answer(
                "❌ Нельзя запланировать рассылку на прошедшее время.\n"
                "Пожалуйста, выберите время позже текущего:"
            )
            return
        
        # Сохраняем дату и время в состоянии
        await state.update_data(schedule_datetime=schedule_datetime)
        
        # Создаем рассылку в базе данных
        await save_scheduled_broadcast(message, state)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат времени.\n"
            "Часы должны быть от 0 до 23, минуты от 0 до 59.\n\n"
            "Попробуйте еще раз:"
        )

async def save_scheduled_broadcast(message: Message, state: FSMContext):
    """Сохраняет запланированную рассылку в базе данных"""
    # Получаем все данные рассылки
    data = await state.get_data()
    
    scheduled_time = data.get("schedule_datetime")
    
    # Создаем запись в базе данных
    async with async_session() as session:
        # Подсчитываем общее количество пользователей
        total_users = await session.scalar(select(func.count()).select_from(User))
        
        # Создаем новую запланированную рассылку
        new_broadcast = Broadcast(
            name=data.get("name"),
            text=data.get("text"),
            photo=data.get("photo"),
            button_text=data.get("button_text"),
            button_url=data.get("button_url"),
            scheduled_at=scheduled_time,
            status="created",
            total_users=total_users
        )
        
        session.add(new_broadcast)
        await session.commit()
    
    # Очищаем состояние
    await state.clear()
    
    await message.answer(
        f"✅ Рассылка успешно запланирована на {scheduled_time.strftime('%d.%m.%Y %H:%M')}!\n\n"
        "Вы можете видеть ее в разделе 'Активные рассылки'.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Активные рассылки", callback_data="active_broadcasts")],
            [InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")]
        ])
    )

async def send_broadcast(bot, broadcast_id: int, admin_id: int):
    """Фоновая задача отправки рассылки всем пользователям"""
    async with async_session() as session:
        # Получаем рассылку
        broadcast_result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        broadcast = broadcast_result.scalar_one_or_none()
        
        if not broadcast:
            logging.error(f"Broadcast {broadcast_id} not found")
            return
        
        # Получаем всех пользователей
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()
        
        # Обновляем общее количество пользователей
        broadcast.total_users = len(users)
        await session.commit()
        
        sent_count = 0
        errors_count = 0
        
        # Отправляем сообщения всем пользователям
        for user in users:
            try:
                # Создаем кнопку для каждого пользователя
                keyboard = None
                if broadcast.button_text and broadcast.button_url:
                    # Создаем простую кнопку с URL
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=broadcast.button_text, url=broadcast.button_url)]
                    ])
                
                # Отправляем сообщение в зависимости от наличия фото
                if broadcast.photo:
                    sent_msg = await bot.send_photo(
                        chat_id=user.telegram_id,
                        photo=broadcast.photo,
                        caption=broadcast.text,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                else:
                    sent_msg = await bot.send_message(
                        chat_id=user.telegram_id,
                        text=broadcast.text,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                
                # Увеличиваем счетчик отправленных
                sent_count += 1
                
                # Добавляем запись о получателе
                recipient = BroadcastRecipient(
                    broadcast_id=broadcast.id,
                    user_id=user.id,
                    received=True,
                    received_at=datetime.now()
                )
                session.add(recipient)
                
                # Обновляем статистику каждые 10 пользователей
                if sent_count % 10 == 0:
                    broadcast.received_count = sent_count
                    await session.commit()
                
                # Делаем небольшую паузу, чтобы не превысить лимиты Telegram
                await asyncio.sleep(0.05)
                
            except Exception as e:
                logging.error(f"Error sending broadcast to user {user.telegram_id}: {e}")
                errors_count += 1
        
        # Обновляем финальную статистику
        broadcast.received_count = sent_count
        broadcast.status = "completed"
        broadcast.sent_at = datetime.now()
        await session.commit()
        
        # Уведомляем админа о завершении рассылки
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"✅ Рассылка '{broadcast.name}' завершена!\n\n"
                    f"Отправлено: {sent_count}/{broadcast.total_users} пользователей\n"
                    f"Ошибок: {errors_count}"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Активные рассылки", callback_data="active_broadcasts")],
                    [InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")]
                ])
            )
        except Exception as e:
            logging.error(f"Error notifying admin about broadcast completion: {e}")

@router.callback_query(F.data == "active_broadcasts")
async def active_broadcasts(callback: CallbackQuery, state: FSMContext):
    """Показывает активные рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    async with async_session() as session:
        # Получаем активные рассылки
        active_broadcasts_query = select(Broadcast).where(
            Broadcast.status.in_(["created", "sending"])
        ).order_by(desc(Broadcast.created_at))
        
        result = await session.execute(active_broadcasts_query)
        broadcasts = result.scalars().all()
        
        if not broadcasts:
            await callback.message.edit_text(
                "📊 Активные рассылки\n\n"
                "В настоящее время нет активных рассылок.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Создать рассылку", callback_data="create_broadcast")],
                    [InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")]
                ])
            )
            await callback.answer()
            return
        
        text = "📊 Активные рассылки:\n\n"
        
        kb = []
        
        for i, broadcast in enumerate(broadcasts, 1):
            status_emoji = "🔄" if broadcast.status == "sending" else "⏳"
            
            text += f"{i}. {status_emoji} {broadcast.name}\n"
            
            if broadcast.scheduled_at:
                text += f"   Запланирована на: {broadcast.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
            
            if broadcast.status == "sending":
                text += f"   Отправлено: {broadcast.received_count}/{broadcast.total_users}\n"
            
            text += "\n"
            
            # Добавляем кнопку для каждой рассылки
            kb.append([InlineKeyboardButton(
                text=f"{status_emoji} {broadcast.name}", 
                callback_data=f"broadcast_details_{broadcast.id}"
            )])
        
        kb.append([InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        
        await callback.answer()

@router.callback_query(F.data.startswith("broadcast_details_"))
async def broadcast_details(callback: CallbackQuery):
    """Показывает детали рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    broadcast_id = int(callback.data.split("_")[-1])
    
    async with async_session() as session:
        # Получаем рассылку
        broadcast_result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        broadcast = broadcast_result.scalar_one_or_none()
        
        if not broadcast:
            await callback.answer("Рассылка не найдена")
            return
        
        # Статус рассылки
        status_emoji = {
            "created": "⏳",
            "sending": "🔄",
            "completed": "✅",
            "failed": "❌"
        }.get(broadcast.status, "❓")
        
        status_text = {
            "created": "Создана",
            "sending": "Отправляется",
            "completed": "Завершена",
            "failed": "Ошибка"
        }.get(broadcast.status, "Неизвестно")
        
        text = (
            f"📊 Детали рассылки '{broadcast.name}'\n\n"
            f"Статус: {status_emoji} {status_text}\n"
            f"Создана: {broadcast.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )
        
        if broadcast.scheduled_at:
            text += f"Запланирована на: {broadcast.scheduled_at.strftime('%d.%m.%Y %H:%M')}\n"
            
        if broadcast.sent_at:
            text += f"Отправлена: {broadcast.sent_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        text += f"\nПолучатели: {broadcast.received_count}/{broadcast.total_users}\n\n"
        
        # Сообщение рассылки (превью)
        text += "📱 Сообщение рассылки:\n\n"
        
        # Ограничиваем длину превью текста
        message_preview = broadcast.text
        if len(message_preview) > 100:
            message_preview = message_preview[:97] + "..."
            
        text += f"{message_preview}\n\n"
        
        # Добавляем информацию о фото и кнопке
        if broadcast.photo:
            text += "🖼 Фото: Прикреплено\n"
            
        if broadcast.button_text and broadcast.button_url:
            text += f"🔘 Кнопка: {broadcast.button_text} ({broadcast.button_url})\n"
        
        # Создаем клавиатуру для управления
        kb = []
        
        # Если рассылка запланирована, добавляем кнопку отправки сейчас
        if broadcast.status == "created" and broadcast.scheduled_at:
            kb.append([InlineKeyboardButton(
                text="📤 Отправить сейчас", 
                callback_data=f"broadcast_send_now_{broadcast.id}"
            )])
            
        # Добавляем кнопку удаления
        kb.append([InlineKeyboardButton(
            text="🗑 Удалить рассылку", 
            callback_data=f"broadcast_delete_{broadcast.id}"
        )])
        
        # Кнопка возврата
        kb.append([InlineKeyboardButton(text="🔙 К активным рассылкам", callback_data="active_broadcasts")])
        
        # Отправляем сообщение
        try:
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            )
        except Exception as e:
            logging.error(f"Error editing message in broadcast_details: {e}")
            # Если текст слишком длинный, отправляем сокращенную версию
            try:
                await callback.message.edit_text(
                    f"📊 Детали рассылки '{broadcast.name}'\n\n"
                    f"Статус: {status_emoji} {status_text}\n"
                    f"Получатели: {broadcast.received_count}/{broadcast.total_users}\n\n"
                    "Сообщение слишком длинное для отображения.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                )
            except Exception as e2:
                logging.error(f"Error sending shortened message: {e2}")
                await callback.answer("Ошибка отображения деталей рассылки")
        
        await callback.answer()

@router.callback_query(F.data.startswith("broadcast_send_now_"))
async def broadcast_send_now_scheduled(callback: CallbackQuery):
    """Отправка запланированной рассылки прямо сейчас"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    broadcast_id = int(callback.data.split("_")[-1])
    
    async with async_session() as session:
        # Получаем рассылку
        broadcast_result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        broadcast = broadcast_result.scalar_one_or_none()
        
        if not broadcast:
            await callback.answer("Рассылка не найдена")
            return
        
        # Проверяем, что рассылка еще не отправлена
        if broadcast.status != "created":
            await callback.answer("Эта рассылка уже в процессе отправки или завершена")
            return
        
        # Меняем статус на "sending"
        broadcast.status = "sending"
        await session.commit()
        
        # Запускаем процесс рассылки
        asyncio.create_task(
            send_broadcast(
                callback.bot, 
                broadcast.id, 
                callback.from_user.id
            )
        )
    
    await callback.message.edit_text(
        "✅ Рассылка запущена!\n\n"
        "Процесс рассылки выполняется в фоновом режиме.\n"
        "Результаты будут доступны в разделе 'Активные рассылки'.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Активные рассылки", callback_data="active_broadcasts")],
            [InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")]
        ])
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("broadcast_delete_"))
async def broadcast_delete(callback: CallbackQuery):
    """Удаление рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    broadcast_id = int(callback.data.split("_")[-1])
    
    # Подтверждение удаления
    await callback.message.edit_text(
        "🗑 Удаление рассылки\n\n"
        "Вы уверены, что хотите удалить эту рассылку?\n"
        "Это действие нельзя отменить.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_broadcast_{broadcast_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"broadcast_details_{broadcast_id}")
            ]
        ])
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_broadcast_"))
async def confirm_delete_broadcast(callback: CallbackQuery):
    """Подтверждение удаления рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    broadcast_id = int(callback.data.split("_")[-1])
    
    async with async_session() as session:
        # Получаем рассылку
        broadcast_result = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        broadcast = broadcast_result.scalar_one_or_none()
        
        if not broadcast:
            await callback.answer("Рассылка не найдена")
            return
        
        # Удаляем получателей рассылки
        await session.execute(
            "DELETE FROM broadcast_recipients WHERE broadcast_id = :broadcast_id",
            {"broadcast_id": broadcast_id}
        )
        
        # Удаляем саму рассылку
        await session.delete(broadcast)
        await session.commit()
    
    await callback.message.edit_text(
        "✅ Рассылка удалена!\n\n"
        "Вы вернулись в меню активных рассылок.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Активные рассылки", callback_data="active_broadcasts")],
            [InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")]
        ])
    )
    
    await callback.answer()

@router.callback_query(F.data == "broadcast_history")
async def broadcast_history(callback: CallbackQuery):
    """История рассылок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    async with async_session() as session:
        # Получаем завершенные рассылки
        history_query = select(Broadcast).where(
            Broadcast.status.in_(["completed", "failed"])
        ).order_by(desc(Broadcast.sent_at)).limit(10)
        
        result = await session.execute(history_query)
        broadcasts = result.scalars().all()
        
        if not broadcasts:
            await callback.message.edit_text(
                "📈 История рассылок\n\n"
                "В истории нет завершенных рассылок.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Создать рассылку", callback_data="create_broadcast")],
                    [InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")]
                ])
            )
            await callback.answer()
            return
        
        text = "📈 История рассылок:\n\n"
        
        kb = []
        
        for i, broadcast in enumerate(broadcasts, 1):
            status_emoji = "✅" if broadcast.status == "completed" else "❌"
            
            text += (
                f"{i}. {status_emoji} {broadcast.name}\n"
                f"   Отправлена: {broadcast.sent_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   Получили: {broadcast.received_count}/{broadcast.total_users}\n\n"
            )
            
            # Добавляем кнопку для каждой рассылки
            kb.append([InlineKeyboardButton(
                text=f"{status_emoji} {broadcast.name}", 
                callback_data=f"broadcast_details_{broadcast.id}"
            )])
        
        kb.append([InlineKeyboardButton(text="🔙 В меню рассылок", callback_data="admin_broadcasts")])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        
        await callback.answer()

@router.callback_query(F.data.startswith("broadcast_stats_"))
async def broadcast_stats(callback: CallbackQuery):
    """Показывает статистику рассылки после завершения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Вызываем детали рассылки
    await broadcast_details(callback)

# Добавляем фоновую задачу для проверки и отправки запланированных рассылок
async def check_scheduled_broadcasts(bot):
    """Периодически проверяет запланированные рассылки и отправляет их при наступлении времени"""
    while True:
        try:
            async with async_session() as session:
                # Получаем запланированные рассылки, время которых уже наступило
                now = datetime.now()
                scheduled_query = select(Broadcast).where(
                    and_(
                        Broadcast.status == "created",
                        Broadcast.scheduled_at <= now
                    )
                )
                
                result = await session.execute(scheduled_query)
                broadcasts = result.scalars().all()
                
                for broadcast in broadcasts:
                    # Меняем статус на "sending"
                    broadcast.status = "sending"
                    await session.commit()
                    
                    # Получаем админский ID из переменных окружения
                    admin_id = int(os.getenv("ADMIN_ID", "5385155120"))
                    
                    # Запускаем отправку
                    asyncio.create_task(send_broadcast(bot, broadcast.id, admin_id))
                    
                    # Уведомляем админа
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=f"🔔 Запланированная рассылка '{broadcast.name}' начала отправку.",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logging.error(f"Error notifying admin about scheduled broadcast: {e}")
        
        except Exception as e:
            logging.error(f"Error checking scheduled broadcasts: {e}")
        
        # Проверяем раз в минуту
        await asyncio.sleep(60)
        
# Функция для запуска фоновой задачи при старте бота
def start_broadcast_scheduler(bot):
    """Запускает планировщик рассылок"""
    asyncio.create_task(check_scheduled_broadcasts(bot)) 