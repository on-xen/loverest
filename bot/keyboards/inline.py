from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
import os
from ..models.models import MenuItem

def get_payment_type_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="💋 Поцелуйчики", callback_data="payment_type:kisses")],
        [InlineKeyboardButton(text="🤗 Обнимашки", callback_data="payment_type:hugs")],
        [InlineKeyboardButton(text="💋+🤗 Оба варианта", callback_data="payment_type:both")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_menu_items_kb(items: List[MenuItem]) -> InlineKeyboardMarkup:
    kb = []
    for item in items:
        payment_info = []
        if item.price_kisses:
            payment_info.append(f"💋{item.price_kisses}")
        if item.price_hugs:
            payment_info.append(f"🤗{item.price_hugs}мин")
        
        button_text = f"{item.name} ({' + '.join(payment_info)})"
        kb.append([InlineKeyboardButton(
            text=button_text[:20],  # Limit to 20 chars
            callback_data=f"view_item:{item.id}"
        )])
    
    kb.append([InlineKeyboardButton(text="🛍️ Корзина", callback_data="view_cart")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_stars_payment_kb() -> InlineKeyboardMarkup:
    amounts = [1, 10, 15, 30, 50, 75, 100, 200, 300, 500, 700, 1000]
    kb = []
    row = []
    
    for amount in amounts:
        if len(row) == 3:
            kb.append(row)
            row = []
        row.append(InlineKeyboardButton(
            text=f"{amount} ⭐️",
            callback_data=f"stars_payment:{amount}"
        ))
    
    if row:
        kb.append(row)
    
    kb.append([InlineKeyboardButton(
        text="💫 Своя сумма",
        callback_data="stars_payment:custom"
    )])
    
    # Добавляем кнопку Boosty, если есть ссылка
    boosty_url = os.getenv("BOOSTY_URL")
    if boosty_url:
        kb.append([InlineKeyboardButton(
            text="🔥 Поддержать на Boosty",
            url=boosty_url
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_start_kb() -> InlineKeyboardMarkup:
    """Клавиатура для стартового экрана"""
    kb = [
        [InlineKeyboardButton(text="🍽️ Создать ресторан", callback_data="create_restaurant")],
        [InlineKeyboardButton(text="🔗 Подключиться к ресторану", callback_data="connect_restaurant")],
        [InlineKeyboardButton(text="🌟 Поддержать", callback_data="support")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb) 