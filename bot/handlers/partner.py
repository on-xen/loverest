from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from ..states.states import RestaurantEntry
from ..models.base import async_session
from ..models.models import User, Restaurant, MenuItem, Order, OrderItem
from ..keyboards.inline import get_menu_items_kb
from ..keyboards.reply import get_main_menu
import os
import logging
import datetime

router = Router()

def create_menu_keyboard(menu_items, with_cart=True):
    """
    Создает клавиатуру с позициями меню в два столбца.
    
    Для четного количества позиций - все в два столбца.
    Для нечетного - все пары в два столбца, последняя позиция занимает целую строку.
    """
    kb = []
    menu_items_count = len(menu_items)
    
    # Обрабатываем по парам, для нечетного количества оставляем последний элемент
    pairs_count = menu_items_count // 2
    has_odd_item = menu_items_count % 2 != 0
    
    # Создаем пары кнопок
    for i in range(pairs_count):
        item1 = menu_items[i*2]
        item2 = menu_items[i*2 + 1]
        
        kb.append([
            InlineKeyboardButton(text=item1.name, callback_data=f"view_item:{item1.id}"),
            InlineKeyboardButton(text=item2.name, callback_data=f"view_item:{item2.id}")
        ])
    
    # Если есть нечетный элемент, добавляем его отдельной строкой
    if has_odd_item:
        last_item = menu_items[-1]
        kb.append([InlineKeyboardButton(text=last_item.name, callback_data=f"view_item:{last_item.id}")])
    
    # Добавляем кнопки корзины и выхода
    if with_cart:
        kb.append([InlineKeyboardButton(text="🛍️ Корзина", callback_data="view_cart")])
    kb.append([InlineKeyboardButton(text="👋 Отключиться", callback_data="leave_restaurant")])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.message(F.text == "🔑 Войти в ресторан")
async def enter_restaurant_start(message: Message, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        
        if user and user.current_restaurant_id:
            result = await session.execute(select(Restaurant).where(Restaurant.id == user.current_restaurant_id))
            restaurant = result.scalar_one_or_none()
            
            # Теперь сразу показываем меню ресторана
            result = await session.execute(select(MenuItem).where(MenuItem.restaurant_id == restaurant.id))
            menu_items = result.scalars().all()
            
            if not menu_items:
                kb = [[InlineKeyboardButton(text="👋 Отключиться", callback_data="leave_restaurant")]]
                await message.answer(
                    f"Вы подключены к ресторану '{restaurant.name}', но меню пока пустое 😔",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                )
                return
            
            # Используем новую функцию для создания клавиатуры меню
            kb = create_menu_keyboard(menu_items)
            
            await message.answer(
                f"Вы подключены к ресторану '{restaurant.name}'.\nВыберите позицию для просмотра:",
                reply_markup=kb
            )
            return
    
    await state.set_state(RestaurantEntry.waiting_for_code)
    await message.answer(
        "Введите код приглашения или перейдите по ссылке-приглашению:"
    )

@router.message(Command("start"))
async def start_with_code(message: Message):
    args = message.text.split()
    if len(args) != 2:
        return
    
    invite_code = args[1].upper()
    await process_restaurant_code(message, invite_code)

@router.message(RestaurantEntry.waiting_for_code)
async def process_restaurant_code_message(message: Message, state: FSMContext):
    await state.clear()
    await process_restaurant_code(message, message.text.upper())

async def process_restaurant_code(message: Message, invite_code: str):
    try:
        async with async_session() as session:
            # Проверяем, что сессия активна и валидна
            if session.is_active:
                # Получаем пользователя
                result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
                user = result.scalar_one_or_none()
                
                if not user:
                    # Если пользователь не найден, создаем его
                    user = User(telegram_id=message.from_user.id)
                    session.add(user)
                    await session.commit()
                    # Получаем пользователя снова после создания
                    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
                    user = result.scalar_one_or_none()
                
                if user.current_restaurant_id:
                    result = await session.execute(select(Restaurant).where(Restaurant.id == user.current_restaurant_id))
                    restaurant = result.scalar_one_or_none()
                    
                    kb = [
                        [InlineKeyboardButton(text="📋 Показать меню", callback_data="show_menu")],
                        [InlineKeyboardButton(text="👋 Отключиться", callback_data="leave_restaurant")]
                    ]
                    await message.answer(
                        f"Вы уже подключены к ресторану '{restaurant.name}'.\n\n"
                        "Сначала отключитесь от текущего ресторана:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                    )
                    return
                
                # Проверяем код приглашения
                result = await session.execute(select(Restaurant).where(Restaurant.invite_code == invite_code))
                restaurant = result.scalar_one_or_none()
                
                if not restaurant:
                    await message.answer("❌ Неверный код приглашения!")
                    return
                
                # Получаем данные о владельце ресторана для уведомления
                result = await session.execute(select(User).where(User.id == restaurant.owner_id))
                owner = result.scalar_one_or_none()
                
                # Обновляем данные пользователя
                user.current_restaurant_id = restaurant.id
                await session.commit()
                
                # Отправляем уведомление владельцу ресторана о новом клиенте
                if owner:
                    try:
                        username = message.from_user.username or "Нет username"
                        user_link = f"@{username}" if username != "Нет username" else f"ID: {message.from_user.id}"
                        
                        await message.bot.send_message(
                            owner.telegram_id,
                            f"🔔 Новый клиент подключился к вашему ресторану '{restaurant.name}'!\n\n"
                            f"Пользователь: {message.from_user.full_name} ({user_link})"
                        )
                    except Exception as e:
                        logging.error(f"Failed to send notification to restaurant owner: {e}")
                
                # Получаем меню после коммита в новой сессии
                async with async_session() as new_session:
                    # Получаем ресторан с меню
                    result = await new_session.execute(
                        select(Restaurant).where(Restaurant.id == restaurant.id)
                    )
                    updated_restaurant = result.scalar_one_or_none()
                    
                    # Получаем позиции меню напрямую
                    result = await new_session.execute(
                        select(MenuItem).where(MenuItem.restaurant_id == restaurant.id)
                    )
                    menu_items = result.scalars().all()
                    
                    if not menu_items:
                        kb = [[InlineKeyboardButton(text="👋 Отключиться", callback_data="leave_restaurant")]]
                        await message.answer(
                            f"✅ Вы успешно подключились к ресторану '{restaurant.name}'!\n"
                            "К сожалению, меню пока пустое 😔",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
                        )
                        return
                    
                    # Используем новую функцию для создания клавиатуры меню
                    kb = create_menu_keyboard(menu_items)
                    
                    await message.answer(
                        f"✅ Добро пожаловать в ресторан '{restaurant.name}'!\n"
                        "Выберите позиции из меню:",
                        reply_markup=kb
                    )
            else:
                # Если сессия не активна, сообщаем об ошибке
                logging.error("SQLAlchemy session is not active")
                await message.answer("Произошла ошибка при подключении к базе данных. Пожалуйста, попробуйте еще раз.")
    except Exception as e:
        # Логируем ошибку и отправляем сообщение пользователю
        logging.error(f"Error in process_restaurant_code: {e}")
        await message.answer("Произошла ошибка при обработке кода ресторана. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "show_menu")
async def show_restaurant_menu(callback: CallbackQuery):
    async with async_session() as session:
        # Получаем пользователя через select вместо get с неправильным параметром
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        
        if not user or not user.current_restaurant_id:
            await callback.answer("Вы не подключены ни к одному ресторану!")
            return
        
        # Получаем ресторан по его ID
        result = await session.execute(select(Restaurant).where(Restaurant.id == user.current_restaurant_id))
        restaurant = result.scalar_one_or_none()
        
        if not restaurant:
            await callback.answer("Ресторан не найден!")
            return
        
        # Получаем позиции меню
        result = await session.execute(select(MenuItem).where(MenuItem.restaurant_id == restaurant.id))
        menu_items = result.scalars().all()
        
        if not menu_items:
            await callback.answer("В меню ресторана пока нет позиций!")
            return
        
        # Используем новую функцию для создания клавиатуры меню
        kb = create_menu_keyboard(menu_items)
        
        # ИЗМЕНЕНИЕ: Всегда удаляем предыдущее сообщение и отправляем новое
        try:
            # Пробуем удалить предыдущее сообщение
            await callback.message.delete()
        except Exception as e:
            logging.error(f"Error deleting previous message: {e}")
        
        # Отправляем новое сообщение с меню
        try:
            await callback.message.answer(
                f"Меню ресторана '{restaurant.name}':\n"
                "Выберите позиции для просмотра деталей:",
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"Error sending new message: {e}")
            # В случае ошибки пробуем отправить новое сообщение напрямую
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=f"Меню ресторана '{restaurant.name}':\n"
                     "Выберите позиции для просмотра деталей:",
                reply_markup=kb
            )
        
        await callback.answer()

# Дополнительная функция для отображения меню, которая принимает ID ресторана
async def show_restaurant_menu(callback: CallbackQuery, restaurant_id: int):
    """Показать меню ресторана по его ID (вызывается из других обработчиков)"""
    async with async_session() as session:
        # Получаем ресторан по ID
        result = await session.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
        restaurant = result.scalar_one_or_none()
        
        if not restaurant:
            await callback.answer("Ресторан не найден!")
            return
        
        # Получаем позиции меню
        result = await session.execute(select(MenuItem).where(MenuItem.restaurant_id == restaurant.id))
        menu_items = result.scalars().all()
        
        if not menu_items:
            await callback.answer("В меню ресторана пока нет позиций!")
            return
        
        # Используем функцию для создания клавиатуры меню
        kb = create_menu_keyboard(menu_items)
        
        # ИЗМЕНЕНИЕ: Всегда удаляем предыдущее сообщение и отправляем новое
        try:
            # Пробуем удалить предыдущее сообщение
            await callback.message.delete()
        except Exception as e:
            logging.error(f"Error deleting previous message: {e}")
        
        # Отправляем новое сообщение с меню
        try:
            await callback.message.answer(
                f"Меню ресторана '{restaurant.name}':\n"
                "Выберите позиции для просмотра деталей:",
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"Error sending new message: {e}")
            # В случае ошибки пробуем отправить новое сообщение напрямую
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=f"Меню ресторана '{restaurant.name}':\n"
                     "Выберите позиции для просмотра деталей:",
                reply_markup=kb
            )

# Обработчик для прямого перехода в меню ресторана по ID
@router.callback_query(F.data.startswith("show_restaurant_menu:"))
async def show_restaurant_menu_by_id(callback: CallbackQuery):
    """Обработчик для перехода к меню ресторана по ID"""
    restaurant_id = int(callback.data.split(":")[1])
    await show_restaurant_menu(callback, restaurant_id=restaurant_id)

@router.callback_query(F.data == "leave_restaurant")
async def leave_restaurant(callback: CallbackQuery):
    async with async_session() as session:
        # Получаем пользователя через select вместо get с неправильным параметром
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        
        if not user or not user.current_restaurant_id:
            await callback.answer("Вы не подключены ни к одному ресторану!")
            return
        
        # Получаем ресторан для уведомления владельца
        result = await session.execute(select(Restaurant).where(Restaurant.id == user.current_restaurant_id))
        restaurant = result.scalar_one_or_none()
        
        if restaurant:
            # Получаем владельца ресторана для уведомления
            result = await session.execute(select(User).where(User.id == restaurant.owner_id))
            owner = result.scalar_one_or_none()
            
            # Отключаем пользователя от ресторана
            user.current_restaurant_id = None
            await session.commit()
            
            # Уведомляем владельца ресторана о том, что клиент отключился
            if owner:
                try:
                    username = callback.from_user.username or "Нет username"
                    user_link = f"@{username}" if username != "Нет username" else f"ID: {callback.from_user.id}"
                    
                    await callback.bot.send_message(
                        owner.telegram_id,
                        f"👋 Клиент отключился от вашего ресторана '{restaurant.name}'.\n\n"
                        f"Пользователь: {callback.from_user.full_name} ({user_link})"
                    )
                except Exception as e:
                    logging.error(f"Failed to notify restaurant owner about client leaving: {e}")
        else:
            # Если ресторан не найден, просто отключаем пользователя
            user.current_restaurant_id = None
            await session.commit()
        
        await callback.message.edit_text("👋 Вы отключились от ресторана!")
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_menu(user)
        )

@router.callback_query(F.data.startswith("view_item:"))
async def view_menu_item(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split(":")[1])
    
    # Получаем текущее состояние, чтобы проверить, не просматриваем ли мы уже этот элемент
    data = await state.get_data()
    current_viewed_item = data.get("current_viewed_item")
    
    # Если пользователь уже просматривает этот элемент, просто отвечаем на callback и выходим
    if current_viewed_item == item_id:
        await callback.answer()
        return
    
    # Сохраняем ID текущего просматриваемого элемента
    await state.update_data(current_viewed_item=item_id)
    
    async with async_session() as session:
        # Получаем позицию меню
        result = await session.execute(select(MenuItem).where(MenuItem.id == item_id))
        item = result.scalar_one_or_none()
        
        if not item:
            await callback.answer("❌ Позиция не найдена!")
            return
        
        # Получаем все позиции меню для сохранения кнопок
        result = await session.execute(select(MenuItem).where(MenuItem.restaurant_id == item.restaurant_id))
        menu_items = result.scalars().all()
        
        # Создаем информацию о позиции
        price_info = []
        if item.price_kisses:
            price_info.append(f"💋 Поцелуйчики: {item.price_kisses}")
        if item.price_hugs:
            price_info.append(f"🤗 Обнимашки: {item.price_hugs} мин")
        
        # Обработка описания, чтобы избежать вывода "None"
        description_text = item.description if item.description else "Без описания"
        
        item_text = (
            f"📋 {item.name}\n\n"
            f"📝 Описание: {description_text}\n\n"
            f"⏱ Продолжительность: {item.duration} мин\n"
            f"{' | '.join(price_info)}"
        )
        
        # Создаем те же кнопки меню, но добавляем кнопку корзины и добавления в корзину
        kb = []
        
        # Кнопка добавления в корзину СВЕРХУ
        kb.append([InlineKeyboardButton(
            text="🛒 Добавить в корзину",
            callback_data=f"add_to_cart:{item.id}"
        )])
        
        # Используем ту же логику для отображения меню в два столбца
        menu_items_count = len(menu_items)
        pairs_count = menu_items_count // 2
        has_odd_item = menu_items_count % 2 != 0
        
        # Создаем пары кнопок
        for i in range(pairs_count):
            item1 = menu_items[i*2]
            item2 = menu_items[i*2 + 1]
            
            kb.append([
                InlineKeyboardButton(text=item1.name, callback_data=f"view_item:{item1.id}"),
                InlineKeyboardButton(text=item2.name, callback_data=f"view_item:{item2.id}")
            ])
        
        # Если есть нечетный элемент, добавляем его отдельной строкой
        if has_odd_item:
            last_item = menu_items[-1]
            kb.append([InlineKeyboardButton(text=last_item.name, callback_data=f"view_item:{last_item.id}")])
        
        # Кнопка корзины внизу
        kb.append([InlineKeyboardButton(text="🛍️ Корзина", callback_data="view_cart")])
        kb.append([InlineKeyboardButton(text="👋 Отключиться", callback_data="leave_restaurant")])
        
        markup = InlineKeyboardMarkup(inline_keyboard=kb)
        
        # ИЗМЕНЕНИЕ: Всегда удалять предыдущее сообщение и отправлять новое
        try:
            # Пробуем удалить предыдущее сообщение
            await callback.message.delete()
        except Exception as e:
            logging.error(f"Error deleting previous message: {e}")
        
        # Если есть фото, отправляем фото, иначе только текст
        try:
            if item.photo:
                await callback.message.answer_photo(
                    photo=item.photo,
                    caption=item_text,
                    reply_markup=markup
                )
            else:
                await callback.message.answer(
                    item_text,
                    reply_markup=markup
                )
        except Exception as e:
            logging.error(f"Error sending new message: {e}")
            # В случае ошибки пробуем отправить новое сообщение напрямую
            if item.photo:
                await callback.bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=item.photo,
                    caption=item_text,
                    reply_markup=markup
                )
            else:
                await callback.bot.send_message(
                    chat_id=callback.from_user.id,
                    text=item_text,
                    reply_markup=markup
                )
        
        # Отвечаем на callback, чтобы убрать "часики"
        await callback.answer()

@router.callback_query(F.data.startswith("add_to_cart:"))
async def add_to_cart(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        # Получаем позицию меню
        result = await session.execute(select(MenuItem).where(MenuItem.id == item_id))
        item = result.scalar_one_or_none()
        
        if not item:
            await callback.answer("❌ Позиция не найдена!")
            return
        
        # Добавляем в корзину
        data = await state.get_data()
        cart = data.get("cart", [])
        cart.append(item_id)
        await state.update_data(cart=cart)
        
        await callback.answer(f"✅ {item.name} добавлено в корзину!")

@router.callback_query(F.data == "view_cart")
async def view_cart(callback: CallbackQuery, state: FSMContext):
    """Просмотр корзины"""
    logging.info(f"view_cart handler called, user_id: {callback.from_user.id}")
    data = await state.get_data()
    cart = data.get("cart", [])
    logging.info(f"Cart contents: {cart}")
    
    if not cart:
        await callback.answer("Корзина пуста!", show_alert=True)
        logging.info("Cart is empty, returning")
        return
    
    # Создаем словарь для подсчета количества каждого товара
    item_counts = {}
    for item_id in cart:
        item_counts[item_id] = item_counts.get(item_id, 0) + 1
    
    async with async_session() as session:
        # Получаем позиции из корзины
        items = []
        total_kisses = 0
        total_hugs = 0
        total_duration = 0
        
        for item_id, count in item_counts.items():
            result = await session.execute(select(MenuItem).where(MenuItem.id == item_id))
            item = result.scalar_one_or_none()
            logging.info(f"Retrieved item {item_id}: {item}")
            
            if item:
                # Умножаем цены на количество
                item_kisses = (item.price_kisses or 0) * count
                item_hugs = (item.price_hugs or 0) * count
                item_duration = (item.duration or 0) * count
                
                items.append({
                    "id": item.id,
                    "name": item.name,
                    "count": count,
                    "kisses": item_kisses,
                    "hugs": item_hugs,
                    "duration": item_duration
                })
                
                total_kisses += item_kisses
                total_hugs += item_hugs
                total_duration += item_duration
        
        # Формируем текст корзины
        cart_text = "🛒 Ваша корзина:\n\n"
        for i, item in enumerate(items, 1):
            cart_text += f"{i}. {item['name']} x{item['count']}"
            price_info = []
            if item['kisses']:
                price_info.append(f"💋{item['kisses']}")
            if item['hugs']:
                price_info.append(f"🤗{item['hugs']}")
            
            if price_info:
                cart_text += f" ({' + '.join(price_info)})"
            cart_text += "\n"
        
        cart_text += "\n"
        if total_kisses:
            cart_text += f"💋 Поцелуйчики: {total_kisses}\n"
        if total_hugs:
            cart_text += f"🤗 Обнимашки: {total_hugs} мин\n"
        if total_duration:
            cart_text += f"⏱ Общее время: {total_duration} мин\n"
        
        logging.info(f"Cart text: {cart_text}")
        
        # Создаем клавиатуру
        kb = [
            [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="confirm_order")],
            [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
            [InlineKeyboardButton(text="◀️ Назад к меню", callback_data=f"show_restaurant_menu:{data.get('current_restaurant_id')}")],
        ]
        
        # ИЗМЕНЕНИЕ: Всегда удаляем предыдущее сообщение и отправляем новое
        try:
            # Пробуем удалить предыдущее сообщение
            await callback.message.delete()
        except Exception as e:
            logging.error(f"Error deleting previous message: {e}")
        
        # Отправляем новое сообщение с корзиной
        try:
            await callback.message.answer(
                cart_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            )
        except Exception as e:
            logging.error(f"Error sending new message: {e}")
            # В случае ошибки пробуем отправить новое сообщение напрямую
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=cart_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
            )
        
        await callback.answer()

@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery, state: FSMContext):
    """Очистка корзины"""
    await state.update_data(cart=[])
    await callback.answer("Корзина очищена!", show_alert=True)
    
    # Возвращаемся к меню ресторана
    data = await state.get_data()
    restaurant_id = data.get("current_restaurant_id")
    if restaurant_id:
        await show_restaurant_menu(callback, restaurant_id=restaurant_id)
    else:
        await callback.message.edit_text(
            "Корзина очищена. Выберите ресторан для продолжения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ На главную", callback_data="start")]
            ])
        )

@router.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    
    if not cart:
        await callback.answer("Корзина пуста!")
        return
    
    async with async_session() as session:
        # Получаем позиции через select
        items = []
        restaurant = None
        owner = None
        
        # Получаем пользователя, который делает заказ
        result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        customer = result.scalar_one_or_none()
        
        if not customer:
            await callback.answer("Ошибка: не удалось найти информацию о пользователе!")
            return
            
        # Получаем информацию о корзине
        item_counts = {}
        for item_id in cart:
            item_counts[item_id] = item_counts.get(item_id, 0) + 1
            
        menu_items = {}
        for item_id in item_counts:
            result = await session.execute(select(MenuItem).where(MenuItem.id == item_id))
            item = result.scalar_one_or_none()
            if item:
                menu_items[item_id] = item
                items.append(item)
                
                # Если это первый элемент, получаем ресторан и владельца
                if not restaurant:
                    result = await session.execute(select(Restaurant).where(Restaurant.id == item.restaurant_id))
                    restaurant = result.scalar_one_or_none()
                    
                    if restaurant:
                        result = await session.execute(select(User).where(User.id == restaurant.owner_id))
                        owner = result.scalar_one_or_none()
        
        if not items or not restaurant or not owner:
            await callback.answer("Не удалось найти все элементы заказа!")
            return
        
        # Calculate totals
        total_kisses = 0
        total_hugs = 0
        total_duration = 0
        
        for item_id, count in item_counts.items():
            if item_id in menu_items:
                item = menu_items[item_id]
                total_kisses += (item.price_kisses or 0) * count
                total_hugs += (item.price_hugs or 0) * count
                total_duration += (item.duration or 0) * count
        
        # Создаем запись о заказе в базе данных
        try:
            # Создаем заказ
            new_order = Order(
                user_id=customer.id,
                restaurant_id=restaurant.id,
                status="pending",
                total_kisses=total_kisses,
                total_hugs=total_hugs,
                total_duration=total_duration
            )
            session.add(new_order)
            await session.flush()  # Чтобы получить ID заказа
            
            # Добавляем позиции заказа
            for item_id, count in item_counts.items():
                if item_id in menu_items:
                    item = menu_items[item_id]
                    order_item = OrderItem(
                        order_id=new_order.id,
                        menu_item_id=item_id,
                        quantity=count,
                        price_kisses=item.price_kisses,
                        price_hugs=item.price_hugs
                    )
                    session.add(order_item)
            
            # Сохраняем изменения
            await session.commit()
            
            # Для колбэка order_ready используем ID из базы данных
            order_id = new_order.id
            logging.info(f"Order created in database with ID: {order_id}")
        except Exception as e:
            logging.error(f"Error creating order in database: {e}")
            # Создаем временный ID для заказа, если не удалось сохранить в базе
            import time
            order_id = f"order_{int(time.time())}_{callback.from_user.id}"
            await session.rollback()
        
        # Сохраняем ID заказа в состоянии пользователя
        await state.update_data(last_order_id=order_id)
        
        # Send order to restaurant owner
        owner_kb = [[InlineKeyboardButton(
            text="✅ Заказ готов", 
            callback_data=f"order_ready:{order_id}:{callback.from_user.id}"
        )]]
        
        order_text = (
            f"🔔 Новый заказ!\n\n"
            f"От: {callback.from_user.full_name} (ID: {callback.from_user.id})\n\n"
            f"Позиции:\n"
        )
        
        for item_id, count in item_counts.items():
            if item_id in menu_items:
                item = menu_items[item_id]
                order_text += f"- {item.name} x{count}\n"
                
        order_text += (
            f"\nИтого:\n"
            f"💋 Поцелуйчики: {total_kisses}\n"
            f"🤗 Обнимашки: {total_hugs} мин\n"
            f"⏱ Общее время: {total_duration} мин"
        )
        
        await callback.bot.send_message(
            owner.telegram_id, 
            order_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=owner_kb)
        )
        
        # Clear cart and notify customer
        await state.update_data(cart=[])
        await callback.message.edit_text(
            f"✅ Заказ отправлен!\n\n"
            f"Ресторан: {restaurant.name}\n\n"
            f"Итого:\n"
            f"💋 Поцелуйчики: {total_kisses}\n"
            f"🤗 Обнимашки: {total_hugs} мин\n"
            f"⏱ Общее время: {total_duration} мин\n\n"
            f"Владелец ресторана уведомит вас, когда заказ будет готов."
        )

@router.callback_query(F.data.startswith("order_ready:"))
async def order_ready(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Ошибка с данными заказа!")
        return
        
    order_id = parts[1]
    customer_id = int(parts[2])
    
    try:
        # Получаем информацию о ресторане
        async with async_session() as session:
            # Получаем пользователя (владельца ресторана)
            result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
            owner = result.scalar_one_or_none()
            
            if not owner:
                await callback.answer("Ошибка: информация о владельце не найдена!")
                return
                
            # Получаем ресторан
            result = await session.execute(select(Restaurant).where(Restaurant.owner_id == owner.id))
            restaurant = result.scalar_one_or_none()
            
            if not restaurant:
                await callback.answer("Ошибка: ресторан не найден!")
                return
                
            # Обновляем статус заказа в базе данных
            try:
                # Пытаемся обработать order_id как число (из базы данных)
                order_db_id = int(order_id)
                result = await session.execute(select(Order).where(Order.id == order_db_id))
                order = result.scalar_one_or_none()
                
                if order:
                    order.status = "completed"
                    order.completed_at = datetime.datetime.utcnow()
                    await session.commit()
                    logging.info(f"Order {order_db_id} marked as completed")
            except (ValueError, TypeError) as e:
                # Если order_id не число или заказ не найден, просто продолжаем
                # Это может быть старый формат ID до создания модели Order
                logging.warning(f"Could not update order status in DB: {e}")
                
        # Отправляем уведомление клиенту
        await callback.bot.send_message(
            customer_id,
            f"🎉 Ваш заказ готов!\n\n"
            f"Ресторан '{restaurant.name}' ждет вас для исполнения заказа."
        )
        
        # Обновляем сообщение владельца
        await callback.message.edit_text(
            f"{callback.message.text}\n\n"
            f"✅ Клиент уведомлен о готовности заказа."
        )
        
        await callback.answer("Клиент уведомлен о готовности заказа!")
    except Exception as e:
        logging.error(f"Ошибка при обработке готовности заказа: {e}")
        # Отправляем уведомление администратору
        try:
            admin_id = int(os.getenv("ADMIN_ID", "5385155120"))
            await callback.bot.send_message(
                admin_id,
                f"❌ Ошибка при обработке кнопки 'Заказ готов'!\n\n"
                f"Ошибка: {str(e)}\n"
                f"Данные: order_id={order_id}, customer_id={customer_id}"
            )
        except Exception:
            pass
            
        await callback.answer("Произошла ошибка! Попробуйте еще раз.") 