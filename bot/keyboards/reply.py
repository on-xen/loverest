from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from ..models.models import User

def get_main_menu(user: User = None) -> ReplyKeyboardMarkup:
    """Главное меню бота"""
    kb = []
    
    if user and user.is_restaurant_owner:
        kb.append([KeyboardButton(text="🍴 Мой ресторан")])
    else:
        kb.append([KeyboardButton(text="🍴 Создать ресторан")])
    
    kb.append([KeyboardButton(text="🔑 Войти в ресторан")])
    kb.append([KeyboardButton(text="🌟 Поддержать")])
    kb.append([KeyboardButton(text="❓ Помощь")])
    
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_restaurant_menu() -> ReplyKeyboardMarkup:
    """Меню ресторана"""
    kb = [
        [KeyboardButton(text="📋 Меню"), KeyboardButton(text="🛒 Корзина")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True) 