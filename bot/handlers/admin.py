from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func, select, desc
from ..models.base import async_session
from ..models.models import User, Restaurant, MenuItem, Donation, Order
from datetime import datetime, timedelta
import os
import logging

router = Router()

# FSM для поиска пользователя
class UserSearch(StatesGroup):
    waiting_for_query = State()

# Админский ID из переменных окружения
ADMIN_ID = int(os.getenv("ADMIN_ID", "5385155120"))

# Функция проверки на админа
def is_admin(telegram_id):
    return telegram_id == ADMIN_ID

# Клавиатура админ-панели
def get_admin_keyboard():
    kb = [
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton(text="🏠 Рестораны", callback_data="admin_restaurants")
        ],
        [
            InlineKeyboardButton(text="💘 Заказы", callback_data="admin_orders"),
            InlineKeyboardButton(text="⭐ Донаты", callback_data="admin_donations")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="📨 Рассылки", callback_data="admin_broadcasts")
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
    
    await message.answer(
        "👑 Панель администратора Love Restaurant\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data == "admin_refresh")
async def admin_refresh(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    try:
        await callback.message.edit_text(
            "👑 Панель администратора Love Restaurant\n\n"
            "Выберите раздел:",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer("Панель обновлена!")
    except Exception as e:
        # Проверяем, не связана ли ошибка с тем, что сообщение не изменилось
        if "message is not modified" in str(e):
            await callback.answer("Панель уже актуальна")
        else:
            logging.error(f"Error refreshing admin panel: {e}")
            await callback.answer("Ошибка при обновлении")

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    async with async_session() as session:
        # Получаем статистику пользователей
        total_users = await session.scalar(select(func.count()).select_from(User))
        
        # Активные пользователи за последние 24 часа
        last_day = datetime.utcnow() - timedelta(days=1)
        active_users_query = select(func.count()).select_from(User).where(User.last_activity >= last_day)
        last_day_active = await session.scalar(active_users_query) or 0
        
        # Пользователи с ресторанами
        restaurant_owners = await session.scalar(
            select(func.count()).select_from(User).where(User.is_restaurant_owner == True)
        )
        
        # Пользователи, подключенные к ресторанам
        connected_users = await session.scalar(
            select(func.count()).select_from(User).where(User.current_restaurant_id != None)
        )
        
        # Новые пользователи за 24 часа
        new_users_query = select(func.count()).select_from(User).where(User.created_at >= last_day)
        last_registered = await session.scalar(new_users_query) or 0
        
        # Получаем 5 последних пользователей
        recent_users_query = select(User).order_by(desc(User.created_at)).limit(5)
        result = await session.execute(recent_users_query)
        recent_users = result.scalars().all()

        recent_users_text = ""
        for i, user in enumerate(recent_users, 1):
            try:
                # Получаем информацию о пользователе из Telegram
                user_info = await callback.bot.get_chat(user.telegram_id)
                username = user_info.username or "Нет username"
                fullname = user_info.full_name or "Без имени"
                user_display = f"{fullname}" + (f" (@{username})" if username != "Нет username" else "")
                recent_users_text += f"{i}. {user_display}\n   🆔 ID: {user.telegram_id}, создан: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            except Exception as e:
                logging.error(f"Failed to get user info: {e}")
                recent_users_text += f"{i}. ID: {user.telegram_id}, создан: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        text = (
            "👥 Статистика пользователей:\n\n"
            f"Всего пользователей: {total_users}\n"
            f"Активных за 24 часа: {last_day_active}\n"
            f"Владельцев ресторанов: {restaurant_owners}\n"
            f"Подключены к ресторанам: {connected_users}\n"
            f"Новых за 24 часа: {last_registered}\n\n"
            "Последние пользователи:\n"
            f"{recent_users_text}\n"
            "Выберите действие:"
        )
        
        kb = [
            [InlineKeyboardButton(text="📑 Список всех пользователей", callback_data="admin_all_users")],
            [InlineKeyboardButton(text="📱 Поиск по ID", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except Exception as e:
            logging.error(f"Error editing message in admin_users: {e}")
            # Если сообщение нельзя отредактировать, отправляем новое
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "admin_restaurants")
async def admin_restaurants(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    async with async_session() as session:
        total_restaurants = await session.scalar(select(func.count()).select_from(Restaurant))
        
        # Получаем список недавно созданных ресторанов
        recent_restaurants_query = select(Restaurant, User).join(
            User, Restaurant.owner_id == User.id
        ).order_by(desc(Restaurant.created_at)).limit(5)
        
        result = await session.execute(recent_restaurants_query)
        recent_restaurants = result.all()
        
        # Подсчет меню-позиций для всех ресторанов
        total_menu_items = await session.scalar(select(func.count()).select_from(MenuItem))
        
        text = (
            "🏠 Статистика ресторанов:\n\n"
            f"Всего ресторанов: {total_restaurants}\n"
            f"Всего позиций в меню: {total_menu_items}\n\n"
            "Недавно созданные рестораны:\n"
        )
        
        if recent_restaurants:
            for i, (restaurant, owner) in enumerate(recent_restaurants, 1):
                menu_count = await session.scalar(
                    select(func.count()).select_from(MenuItem).where(
                        MenuItem.restaurant_id == restaurant.id
                    )
                )
                
                # Получаем информацию о владельце из Telegram
                try:
                    owner_info = await callback.bot.get_chat(owner.telegram_id)
                    username = owner_info.username or "Нет username"
                    fullname = owner_info.full_name or "Без имени"
                    owner_display = f"{fullname}" + (f" (@{username})" if username != "Нет username" else "")
                except Exception as e:
                    logging.error(f"Failed to get owner info: {e}")
                    owner_display = f"ID: {owner.telegram_id}"
                
                text += (
                    f"{i}. '{restaurant.name}'\n"
                    f"   Владелец: {owner_display} (ID: {owner.telegram_id})\n"
                    f"   Создан: {restaurant.created_at.strftime('%d.%m.%Y')}\n"
                    f"   Позиций в меню: {menu_count}\n"
                )
        else:
            text += "Нет ресторанов\n"
        
        kb = [
            [InlineKeyboardButton(text="📑 Список всех ресторанов", callback_data="admin_all_restaurants")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except Exception as e:
            logging.error(f"Error editing message in admin_restaurants: {e}")
            # Если не удалось отредактировать сообщение, отправляем новое
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    async with async_session() as session:
        # Проверяем существование таблицы Order
        try:
            # Получаем общее количество заказов
            total_orders = await session.scalar(select(func.count()).select_from(Order))
            
            # Заказы за последние 24 часа
            last_day = datetime.utcnow() - timedelta(days=1)
            recent_orders = await session.scalar(
                select(func.count()).select_from(Order).where(
                    Order.created_at >= last_day
                )
            ) or 0
            
            # Получаем последние 5 заказов с деталями
            recent_orders_query = select(Order, User, Restaurant).join(
                User, Order.user_id == User.id
            ).join(
                Restaurant, Order.restaurant_id == Restaurant.id
            ).order_by(desc(Order.created_at)).limit(5)
            
            result = await session.execute(recent_orders_query)
            last_orders = result.all()
            
            text = (
                "💘 Статистика заказов:\n\n"
                f"Всего заказов: {total_orders}\n"
                f"Заказов за 24 часа: {recent_orders}\n\n"
                "Последние заказы:\n"
            )
            
            if last_orders:
                for i, (order, user, restaurant) in enumerate(last_orders, 1):
                    # Получаем информацию о пользователе из Telegram
                    try:
                        user_info = await callback.bot.get_chat(user.telegram_id)
                        username = user_info.username or "Нет username"
                        fullname = user_info.full_name or "Без имени"
                        user_display = f"{fullname}" + (f" (@{username})" if username != "Нет username" else "")
                    except Exception as e:
                        logging.error(f"Failed to get user info: {e}")
                        user_display = f"ID: {user.telegram_id}"
                    
                    text += (
                        f"{i}. Ресторан: '{restaurant.name}'\n"
                        f"   Пользователь: {user_display} (ID: {user.telegram_id})\n"
                        f"   Сумма: {order.total_kisses or 0} поцелуев, {order.total_hugs or 0} мин обнимашек\n"
                        f"   Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                    )
            else:
                text += "Нет заказов\n"
        except Exception as e:
            logging.error(f"Error querying orders: {e}")
            text = (
                "💘 Статистика заказов:\n\n"
                "В настоящее время информация о заказах недоступна.\n"
                "Заказы обрабатываются в реальном времени через колбэки.\n\n"
            )
        
        kb = [
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except Exception as e:
            logging.error(f"Error editing message in admin_orders: {e}")
            # Если не удалось отредактировать сообщение, отправляем новое
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "admin_donations")
async def admin_donations(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    async with async_session() as session:
        # Статистика донатов
        total_donations = await session.scalar(select(func.count()).select_from(Donation))
        total_amount = await session.scalar(select(func.sum(Donation.amount)).select_from(Donation)) or 0
        
        # Последние донаты
        recent_donations_query = select(Donation, User).join(User).order_by(desc(Donation.created_at)).limit(5)
        result = await session.execute(recent_donations_query)
        recent_donations = result.all()
        
        text = (
            "⭐ Статистика донатов:\n\n"
            f"Всего пожертвований: {total_donations}\n"
            f"Сумма: {total_amount} звезд\n\n"
            "Последние пожертвования:\n"
        )
        
        for i, (donation, user) in enumerate(recent_donations, 1):
            # Получаем информацию о пользователе из Telegram
            try:
                user_info = await callback.bot.get_chat(user.telegram_id)
                username = user_info.username or "Нет username"
                fullname = user_info.full_name or "Без имени"
                user_display = f"{fullname}" + (f" (@{username})" if username != "Нет username" else "")
            except Exception as e:
                logging.error(f"Failed to get user info: {e}")
                user_display = f"ID: {user.telegram_id}"
                
            comment_text = donation.comment if donation.comment else "без комментария"
            donation_text = (
                f"{i}. {user_display} (ID: {user.telegram_id})\n"
                f"   Сумма: {donation.amount} звезд\n"
                f"   Комментарий: {comment_text[:30]}\n"
                f"   Дата: {donation.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
            text += donation_text
        
        if not recent_donations:
            text += "Пока нет пожертвований\n"
        
        kb = [
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except Exception as e:
            logging.error(f"Error editing message in admin_donations: {e}")
            # Если не удалось отредактировать сообщение, отправляем новое
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Собираем статистику
    async with async_session() as session:
        # Статистика пользователей
        total_users = await session.scalar(select(func.count()).select_from(User))
        
        # Активные пользователи за последние 24 часа
        last_day = datetime.utcnow() - timedelta(days=1)
        active_users_query = select(func.count()).select_from(User).where(User.last_activity >= last_day)
        last_day_active = await session.scalar(active_users_query) or 0
        
        # Рестораны
        total_restaurants = await session.scalar(select(func.count()).select_from(Restaurant))
        
        # Позиции в меню
        total_menu_items = await session.scalar(select(func.count()).select_from(MenuItem))
        
        # Заказы
        total_orders = await session.scalar(select(func.count()).select_from(Order))
        
        # Донаты
        total_donations = await session.scalar(select(func.count()).select_from(Donation))
        total_donation_amount = await session.scalar(select(func.sum(Donation.amount)).select_from(Donation)) or 0
        
        text = (
            "📊 Общая статистика бота:\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"👥 Активных за 24 часа: {last_day_active}\n\n"
            f"🏠 Всего ресторанов: {total_restaurants}\n"
            f"🍔 Всего позиций в меню: {total_menu_items}\n\n"
            f"💘 Всего заказов: {total_orders}\n\n"
            f"⭐ Всего пожертвований: {total_donations}\n"
            f"⭐ На сумму: {total_donation_amount} звезд\n"
        )
    
    kb = [
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ]
    
    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception as e:
        logging.error(f"Error editing message in admin_stats: {e}")
        # Если не удалось отредактировать сообщение, отправляем новое
        await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "admin_all_users")
async def admin_all_users(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Получим страницу из состояния или начнем с 1
    data = await state.get_data()
    page = data.get('users_page', 1)
    
    users_per_page = 10
    offset = (page - 1) * users_per_page
    
    async with async_session() as session:
        # Получаем общее количество пользователей
        total_users = await session.scalar(select(func.count()).select_from(User))
        
        # Получаем пользователей для текущей страницы
        users_query = select(User).order_by(desc(User.created_at)).offset(offset).limit(users_per_page)
        result = await session.execute(users_query)
        users = result.scalars().all()
        
        # Общее количество страниц
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        text = f"👥 Список пользователей (страница {page} из {total_pages}):\n\n"
        
        for i, user in enumerate(users, offset + 1):
            # Определяем статус пользователя
            status = []
            if user.is_restaurant_owner:
                status.append("владелец")
            if user.current_restaurant_id:
                status.append("подключен")
            
            status_text = ", ".join(status) if status else "обычный"
            last_activity = user.last_activity.strftime("%d.%m.%Y %H:%M") if user.last_activity else "нет данных"
            
            # Получаем информацию о пользователе из Telegram
            try:
                user_info = await callback.bot.get_chat(user.telegram_id)
                username = user_info.username or "Нет username"
                fullname = user_info.full_name or "Без имени"
                user_display = f"{fullname}" + (f" (@{username})" if username != "Нет username" else "")
            except Exception as e:
                logging.error(f"Failed to get user info: {e}")
                user_display = f"ID: {user.telegram_id}"
            
            # Добавляем базовую информацию
            user_info_text = (
                f"{i}. {user_display}\n"
                f"   🆔 ID: {user.telegram_id}\n"
                f"   📊 Статус: {status_text}\n"
            )
            
            # Если пользователь владелец ресторана, добавляем информацию о его ресторане
            if user.is_restaurant_owner:
                # Получаем ресторан пользователя
                restaurant_query = select(Restaurant).where(Restaurant.owner_id == user.id)
                result = await session.execute(restaurant_query)
                restaurant = result.scalar_one_or_none()
                
                if restaurant:
                    user_info_text += f"   🍴 Владеет рестораном: '{restaurant.name}' (ID: {restaurant.id})\n"
            
            # Если пользователь подключен к ресторану, добавляем информацию об этом ресторане
            if user.current_restaurant_id:
                # Получаем ресторан, к которому подключен пользователь
                connected_query = select(Restaurant).where(Restaurant.id == user.current_restaurant_id)
                result = await session.execute(connected_query)
                connected_restaurant = result.scalar_one_or_none()
                
                if connected_restaurant:
                    user_info_text += f"   🔑 Подключен к ресторану: '{connected_restaurant.name}' (ID: {connected_restaurant.id})\n"
            
            # Добавляем информацию о регистрации и активности
            user_info_text += (
                f"   📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n"
                f"   ⏱ Активность: {last_activity}\n\n"
            )
            
            text += user_info_text
        
        # Кнопки пагинации
        kb = []
        
        # Добавляем кнопки навигации
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users_prev"))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data="admin_users_next"))
        
        if nav_buttons:
            kb.append(nav_buttons)
        
        kb.append([InlineKeyboardButton(text="🔙 В меню пользователей", callback_data="admin_users")])
        
        # Сохраняем текущую страницу в состоянии
        await state.update_data(users_page=page)
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except Exception as e:
            logging.error(f"Error editing message: {e}")
            # Если не удалось отредактировать сообщение, отправляем новое
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "admin_users_prev")
async def admin_users_prev_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    data = await state.get_data()
    current_page = data.get('users_page', 1)
    
    if current_page > 1:
        await state.update_data(users_page=current_page - 1)
        await admin_all_users(callback, state)
    else:
        await callback.answer("Вы уже на первой странице")

@router.callback_query(F.data == "admin_users_next")
async def admin_users_next_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    data = await state.get_data()
    current_page = data.get('users_page', 1)
    
    async with async_session() as session:
        total_users = await session.scalar(select(func.count()).select_from(User))
        users_per_page = 10
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        if current_page < total_pages:
            await state.update_data(users_page=current_page + 1)
            await admin_all_users(callback, state)
        else:
            await callback.answer("Вы уже на последней странице")

@router.callback_query(F.data == "admin_all_restaurants")
async def admin_all_restaurants(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Получим страницу из состояния или начнем с 1
    data = await state.get_data()
    page = data.get('restaurants_page', 1)
    
    restaurants_per_page = 5
    offset = (page - 1) * restaurants_per_page
    
    async with async_session() as session:
        # Получаем общее количество ресторанов
        total_restaurants = await session.scalar(select(func.count()).select_from(Restaurant))
        
        # Получаем рестораны для текущей страницы с владельцами
        restaurants_query = select(Restaurant, User).join(
            User, Restaurant.owner_id == User.id
        ).order_by(desc(Restaurant.created_at)).offset(offset).limit(restaurants_per_page)
        
        result = await session.execute(restaurants_query)
        restaurants_with_owners = result.all()
        
        # Общее количество страниц
        total_pages = (total_restaurants + restaurants_per_page - 1) // restaurants_per_page
        
        text = f"🏠 Список ресторанов (страница {page} из {total_pages}):\n\n"
        
        for i, (restaurant, owner) in enumerate(restaurants_with_owners, offset + 1):
            # Получаем количество позиций в меню
            menu_count = await session.scalar(
                select(func.count()).select_from(MenuItem).where(
                    MenuItem.restaurant_id == restaurant.id
                )
            )
            
            # Получаем информацию о владельце из Telegram
            try:
                owner_info = await callback.bot.get_chat(owner.telegram_id)
                username = owner_info.username or "Нет username"
                fullname = owner_info.full_name or "Без имени"
                owner_display = f"{fullname}" + (f" (@{username})" if username != "Нет username" else "")
            except Exception as e:
                logging.error(f"Failed to get owner info: {e}")
                owner_display = f"ID: {owner.telegram_id}"
            
            # Считаем количество подключенных клиентов
            clients_count = await session.scalar(
                select(func.count()).select_from(User).where(
                    User.current_restaurant_id == restaurant.id
                )
            )
            
            text += (
                f"{i}. '{restaurant.name}'\n"
                f"   👤 Владелец: {owner_display}\n"
                f"   🆔 ID владельца: {owner.telegram_id}\n"
                f"   🔑 Код приглашения: {restaurant.invite_code}\n"
                f"   📋 Позиций в меню: {menu_count}\n"
                f"   👥 Подключенных клиентов: {clients_count}\n"
                f"   📅 Создан: {restaurant.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        
        if not restaurants_with_owners:
            text += "Нет ресторанов\n"
        
        # Кнопки пагинации
        kb = []
        
        # Добавляем кнопки навигации
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_restaurants_prev"))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data="admin_restaurants_next"))
        
        if nav_buttons:
            kb.append(nav_buttons)
        
        kb.append([InlineKeyboardButton(text="🔙 В меню ресторанов", callback_data="admin_restaurants")])
        
        # Сохраняем текущую страницу в состоянии
        await state.update_data(restaurants_page=page)
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except Exception as e:
            logging.error(f"Error editing message in admin_all_restaurants: {e}")
            # Если не удалось отредактировать сообщение, отправляем новое
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "admin_restaurants_prev")
async def admin_restaurants_prev_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    data = await state.get_data()
    current_page = data.get('restaurants_page', 1)
    
    if current_page > 1:
        await state.update_data(restaurants_page=current_page - 1)
        await admin_all_restaurants(callback, state)
    else:
        await callback.answer("Вы уже на первой странице")

@router.callback_query(F.data == "admin_restaurants_next")
async def admin_restaurants_next_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    data = await state.get_data()
    current_page = data.get('restaurants_page', 1)
    
    async with async_session() as session:
        total_restaurants = await session.scalar(select(func.count()).select_from(Restaurant))
        restaurants_per_page = 5
        total_pages = (total_restaurants + restaurants_per_page - 1) // restaurants_per_page
        
        if current_page < total_pages:
            await state.update_data(restaurants_page=current_page + 1)
            await admin_all_restaurants(callback, state)
        else:
            await callback.answer("Вы уже на последней странице")

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    # Получаем статистику для главной панели
    async with async_session() as session:
        total_users = await session.scalar(select(func.count()).select_from(User))
        restaurant_owners = await session.scalar(
            select(func.count()).select_from(User).where(User.is_restaurant_owner == True)
        )
        total_restaurants = await session.scalar(select(func.count()).select_from(Restaurant))
    
    text = (
        "👨‍💼 Панель администратора:\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Владельцев ресторанов: {restaurant_owners}\n"
        f"Всего ресторанов: {total_restaurants}\n\n"
        "Выберите раздел:"
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_keyboard())
    except Exception as e:
        logging.error(f"Error editing message in admin_back: {e}")
        # Если сообщение нельзя отредактировать, отправляем новое
        await callback.message.answer(text, reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin_search_user")
async def admin_search_user(callback: CallbackQuery, state: FSMContext):
    """Начало поиска пользователя по ID"""
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа к этой функции")
        return
    
    await state.set_state(UserSearch.waiting_for_query)
    
    try:
        await callback.message.edit_text(
            "🔍 Поиск пользователя\n\n"
            "Введите Telegram ID пользователя (цифры) или @username пользователя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users")]
            ])
        )
    except Exception as e:
        logging.error(f"Error editing message in admin_search_user: {e}")
        # Если не удалось отредактировать сообщение, отправляем новое
        await callback.message.answer(
            "🔍 Поиск пользователя\n\n"
            "Введите Telegram ID пользователя (цифры) или @username пользователя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users")]
            ])
        )
    
    await callback.answer()

@router.message(UserSearch.waiting_for_query)
async def process_user_search(message: Message, state: FSMContext):
    """Обработка поискового запроса"""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции")
        return
    
    search_query = message.text.strip()
    
    # Проверяем, что ввел пользователь - ID или username
    if search_query.isdigit():
        # Поиск по ID
        user_tg_id = int(search_query)
        await find_user_by_telegram_id(message, user_tg_id, state)
    elif search_query.startswith('@'):
        # Поиск по username
        username = search_query[1:]  # убираем @
        await find_user_by_username(message, username, state)
    else:
        # Неверный формат
        await message.answer(
            "❌ Неверный формат запроса!\n"
            "Введите Telegram ID пользователя (цифры) или @username пользователя",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад к поиску", callback_data="admin_search_user")],
                [InlineKeyboardButton(text="🔙 В меню пользователей", callback_data="admin_users")]
            ])
        )

async def find_user_by_telegram_id(message: Message, telegram_id: int, state: FSMContext):
    """Поиск пользователя по Telegram ID"""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        
        if user:
            await show_user_profile(message, user, state)
        else:
            # Пользователь не найден в базе
            await message.answer(
                f"❌ Пользователь с ID {telegram_id} не найден в базе данных.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад к поиску", callback_data="admin_search_user")],
                    [InlineKeyboardButton(text="🔙 В меню пользователей", callback_data="admin_users")]
                ])
            )

async def find_user_by_username(message: Message, username: str, state: FSMContext):
    """Поиск пользователя по username"""
    # Здесь мы будем искать всех пользователей в БД и проверять username через Telegram API
    async with async_session() as session:
        # Получаем всех пользователей
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        found_user = None
        
        # Ищем пользователя с нужным username
        for user in users:
            try:
                user_info = await message.bot.get_chat(user.telegram_id)
                if user_info.username and user_info.username.lower() == username.lower():
                    found_user = user
                    break
            except Exception as e:
                logging.error(f"Failed to get user info for {user.telegram_id}: {e}")
        
        if found_user:
            await show_user_profile(message, found_user, state)
        else:
            # Пользователь не найден
            await message.answer(
                f"❌ Пользователь с username @{username} не найден в базе данных.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад к поиску", callback_data="admin_search_user")],
                    [InlineKeyboardButton(text="🔙 В меню пользователей", callback_data="admin_users")]
                ])
            )

async def show_user_profile(message: Message, user: User, state: FSMContext):
    """Показать профиль пользователя"""
    await state.clear()  # Очищаем состояние
    
    async with async_session() as session:
        # Определяем статус пользователя
        status = []
        if user.is_restaurant_owner:
            status.append("владелец ресторана")
            
            # Получаем ресторан пользователя
            restaurant_query = select(Restaurant).where(Restaurant.owner_id == user.id)
            result = await session.execute(restaurant_query)
            restaurant = result.scalar_one_or_none()
            
            if restaurant:
                restaurant_info = f"🍴 Ресторан: {restaurant.name} (ID: {restaurant.id})\n" \
                                f"📅 Создан: {restaurant.created_at.strftime('%d.%m.%Y %H:%M')}\n" \
                                f"🔑 Код приглашения: {restaurant.invite_code}\n"
                
                # Счетчик позиций в меню
                menu_count_query = select(func.count()).select_from(MenuItem).where(MenuItem.restaurant_id == restaurant.id)
                menu_count = await session.scalar(menu_count_query) or 0
                restaurant_info += f"📋 Позиций в меню: {menu_count}\n"
                
                # Счетчик клиентов
                clients_count_query = select(func.count()).select_from(User).where(User.current_restaurant_id == restaurant.id)
                clients_count = await session.scalar(clients_count_query) or 0
                restaurant_info += f"👥 Клиентов: {clients_count}\n"
            else:
                restaurant_info = "🍴 Ресторан не найден (возможно, удален)\n"
        else:
            restaurant_info = ""
        
        # Проверяем, подключен ли пользователь к ресторану
        if user.current_restaurant_id:
            status.append("клиент ресторана")
            
            # Получаем ресторан, к которому подключен
            connected_restaurant_query = select(Restaurant).where(Restaurant.id == user.current_restaurant_id)
            result = await session.execute(connected_restaurant_query)
            connected_restaurant = result.scalar_one_or_none()
            
            if connected_restaurant:
                connected_info = f"🔗 Подключен к ресторану: {connected_restaurant.name}\n"
            else:
                connected_info = "🔗 Подключен к несуществующему ресторану\n"
        else:
            connected_info = ""
            
        if not status:
            status.append("обычный пользователь")
        
        status_text = ", ".join(status)
        
        # Получаем информацию о пользователе из Telegram
        try:
            user_info = await message.bot.get_chat(user.telegram_id)
            username = user_info.username or "Нет username"
            fullname = user_info.full_name or "Без имени"
            user_display = f"{fullname}" + (f" (@{username})" if username != "Нет username" else "")
            
            # Проверяем, есть ли у пользователя фото
            photos = await message.bot.get_user_profile_photos(user.telegram_id, limit=1)
            has_photo = photos.total_count > 0
        except Exception as e:
            logging.error(f"Failed to get user info: {e}")
            user_display = f"ID: {user.telegram_id}"
            has_photo = False
        
        # Форматируем информацию о пользователе
        last_activity = user.last_activity.strftime("%d.%m.%Y %H:%M") if user.last_activity else "нет данных"
        
        text = (
            f"👤 Профиль пользователя: {user_display}\n\n"
            f"🆔 Telegram ID: {user.telegram_id}\n"
            f"📊 Статус: {status_text}\n"
            f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"⏱ Последняя активность: {last_activity}\n\n"
        )
        
        # Добавляем информацию о ресторане, если есть
        if restaurant_info:
            text += f"📌 Информация о ресторане:\n{restaurant_info}\n"
        
        # Добавляем информацию о подключении, если есть
        if connected_info:
            text += f"📌 Подключение:\n{connected_info}\n"
        
        # Создаем клавиатуру с действиями
        kb = [
            [InlineKeyboardButton(text="◀️ Назад к поиску", callback_data="admin_search_user")],
            [InlineKeyboardButton(text="🔙 В меню пользователей", callback_data="admin_users")]
        ]
        
        # Если у пользователя есть фото, отправляем с фото
        if has_photo:
            try:
                await message.answer_photo(
                    photos.photos[0][-1].file_id,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                )
            except Exception as e:
                logging.error(f"Failed to send photo: {e}")
                await message.answer(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                )
        else:
            await message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            ) 