from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import os

from ..models.base import async_session
from ..models.models import User, Restaurant
from ..keyboards.reply import get_main_menu
from ..keyboards.inline import get_start_kb

router = Router()

# Получаем имя пользователя администратора из переменных окружения
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "LoveRestaurantAdmin")

@router.message(CommandStart())
async def start_command(message: Message):
    """Обработчик команды /start"""
    logging.info(f"Start command received from user {message.from_user.id} (@{message.from_user.username or 'no_username'})")
    
    # Проверяем наличие аргумента (инвайт-кода)
    args = message.text.split()
    invite_code = None
    
    if len(args) > 1:
        invite_code = args[1]
        logging.info(f"Invite code detected: {invite_code}")
    
    async with async_session() as session:
        # Проверяем, есть ли пользователь в базе
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        
        if not user:
            # Создаем нового пользователя
            user = User(telegram_id=message.from_user.id)
            session.add(user)
            await session.commit()
            logging.info(f"New user created: {message.from_user.id}")
        
        # Если есть инвайт-код, пытаемся подключиться к ресторану
        if invite_code:
            result = await session.execute(select(Restaurant).where(Restaurant.invite_code == invite_code))
            restaurant = result.scalar_one_or_none()
            
            if restaurant:
                # Подключаем пользователя к ресторану
                user.current_restaurant_id = restaurant.id
                await session.commit()
                logging.info(f"User {message.from_user.id} connected to restaurant {restaurant.id} ({restaurant.name})")
                
                await message.answer(
                    f"Вы успешно подключились к ресторану '{restaurant.name}'!\n"
                    f"Теперь вы можете просматривать меню и делать заказы.",
                    reply_markup=get_main_menu()
                )
                return
            else:
                logging.warning(f"Invalid invite code used: {invite_code}")
                await message.answer(
                    "Неверный код приглашения. Проверьте код и попробуйте снова.",
                    reply_markup=get_main_menu()
                )
                return
    
    # Отправляем приветственное сообщение с reply-клавиатурой
    await message.answer(
        "Добро пожаловать в Love Restaurant!\n\n"
        "Здесь вы можете создать свой виртуальный ресторан любви, "
        "где валютой служат поцелуи и обнимашки.",
        reply_markup=get_main_menu(user)
    )

@router.message(F.text == "❓ Помощь")
@router.message(Command("help"))
async def help_command(message: Message):
    """Обработчик команды /help и кнопки Помощь"""
    logging.info(f"Help command received from user {message.from_user.id}")
    
    await message.answer(
        "📖 Справка по боту Love Restaurant:\n\n"
        "🍽 <b>Создание ресторана</b>\n"
        "Нажмите кнопку 'Создать ресторан' и следуйте инструкциям.\n\n"
        "🔗 <b>Подключение к ресторану</b>\n"
        "Используйте код приглашения или ссылку от владельца ресторана.\n\n"
        "📋 <b>Управление меню</b>\n"
        "Владельцы ресторанов могут добавлять, редактировать и удалять позиции в меню.\n\n"
        "💋 <b>Валюта</b>\n"
        "В наших ресторанах расплачиваются поцелуями и минутами обнимашек.\n\n"
        "🛒 <b>Заказы</b>\n"
        "Выбирайте позиции, добавляйте их в корзину и оформляйте заказ.\n\n"
        "❓ <b>Команды</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n\n"
        f"Если у вас остались вопросы, обратитесь к <a href='https://t.me/{ADMIN_USERNAME}'>администратору</a>.",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# Удаляем обработчики инлайн-кнопок, так как теперь используем reply-клавиатуру
# @router.callback_query(F.data == "help")
# async def help_callback(callback: CallbackQuery):
#     """Обработчик кнопки 'Помощь'"""
#     ...
# 
# @router.callback_query(F.data == "start")
# async def start_callback(callback: CallbackQuery):
#     """Обработчик кнопки 'Начать'"""
#     ...