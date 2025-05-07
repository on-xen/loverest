import os
import traceback
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
import datetime

class ErrorMonitorMiddleware(BaseMiddleware):
    """
    Middleware для мониторинга и логирования ошибок.
    В случае критических ошибок отправляет уведомление администратору.
    """
    
    def __init__(self):
        self.admin_id = int(os.getenv("ADMIN_ID", "5385155120"))
        self.admin_username = os.getenv("ADMIN_USERNAME", "LoveRestaurantAdmin")
        self.last_error_time = {}  # error_hash -> last_notification_time
        self.error_cooldown = 300  # Не отправлять повторные уведомления о той же ошибке чаще чем раз в 5 минут
        # Список некритичных ошибок, о которых не нужно уведомлять
        self.non_critical_errors = [
            "message is not modified",
            "query is too old",
            "message to edit not found",
            "message to delete not found",
            "message can't be deleted",
            "bot was blocked by the user"
        ]
        logging.info(f"ErrorMonitorMiddleware initialized with admin_id={self.admin_id}")
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            # Пытаемся выполнить обработчик
            return await handler(event, data)
        except Exception as e:
            # Проверяем, является ли ошибка некритичной
            error_message_lower = str(e).lower()
            is_non_critical = any(err in error_message_lower for err in self.non_critical_errors)
            
            # Для некритичных ошибок, таких как "message is not modified", просто логируем и возвращаем
            if is_non_critical:
                logging.info(f"Non-critical error: {e}")
                
                # Если это callback-запрос, отвечаем на него, чтобы убрать "часики"
                if isinstance(event, CallbackQuery):
                    if "message is not modified" in error_message_lower:
                        try:
                            await event.answer("Данные уже актуальны")
                        except Exception:
                            pass
                    else:
                        try:
                            await event.answer()
                        except Exception:
                            pass
                
                # Не пробрасываем некритичные ошибки дальше
                return None
            
            # Получаем трассировку ошибки
            tb = traceback.format_exc()
            error_hash = hash(str(e) + str(type(e)))
            
            # Логируем ошибку
            logging.error(f"Uncaught exception: {e}\n{tb}")
            
            # Формируем сообщение для администратора
            error_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_message = f"⚠️ Критическая ошибка в боте!\n\n"
            error_message += f"Время: {error_time}\n"
            error_message += f"Тип: {type(e).__name__}\n"
            error_message += f"Сообщение: {str(e)}\n\n"
            
            # Добавляем информацию о пользователе, если доступна
            user_info = "Неизвестный пользователь"
            if isinstance(event, Message) or isinstance(event, CallbackQuery):
                user = event.from_user
                user_info = f"{user.full_name} (@{user.username or 'нет'}, ID: {user.id})"
                
                # Добавляем контекст события
                if isinstance(event, Message):
                    if event.text:
                        error_message += f"Сообщение: {event.text[:100]}\n"
                    elif event.caption:
                        error_message += f"Подпись: {event.caption[:100]}\n"
                elif isinstance(event, CallbackQuery):
                    error_message += f"Callback data: {event.data}\n"
            
            error_message += f"Пользователь: {user_info}\n\n"
            
            # Добавляем трассировку (ограничиваем длину)
            tb_short = tb.split("\n")[-10:] if len(tb.split("\n")) > 10 else tb.split("\n")
            error_message += "Трассировка:\n<code>" + "\n".join(tb_short) + "</code>"
            
            # Проверяем, не отправляли ли мы уже уведомление о такой ошибке недавно
            current_time = datetime.datetime.now().timestamp()
            should_notify = True
            
            if error_hash in self.last_error_time:
                if current_time - self.last_error_time[error_hash] < self.error_cooldown:
                    should_notify = False
            
            if should_notify:
                # Отправляем уведомление администратору
                bot = data.get("bot")
                if bot:
                    try:
                        await bot.send_message(
                            self.admin_id,
                            error_message,
                            parse_mode="HTML"
                        )
                        self.last_error_time[error_hash] = current_time
                        logging.info(f"Error notification sent to admin: {error_hash}")
                    except Exception as notify_error:
                        logging.error(f"Failed to send error notification: {notify_error}")
            
            # Создаем клавиатуру со ссылкой на администратора
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📞 Связаться с поддержкой", url=f"https://t.me/{self.admin_username}")]
            ])
            
            # Если это сообщение от пользователя, отправляем ему уведомление о проблеме
            if isinstance(event, Message):
                try:
                    await event.answer(
                        "❌ Произошла ошибка при обработке запроса.\nАдминистратор уже уведомлен о проблеме. Пожалуйста, попробуйте позже или обратитесь в поддержку.",
                        reply_markup=kb
                    )
                except Exception as user_notify_error:
                    logging.error(f"Failed to send error notification to user: {user_notify_error}")
            elif isinstance(event, CallbackQuery):
                try:
                    # Сначала отправляем уведомление через callback
                    await event.answer(
                        "❌ Произошла ошибка. Попробуйте позже.", 
                        show_alert=True
                    )
                    
                    # Затем отправляем более детальное сообщение с кнопкой
                    await event.message.answer(
                        "❌ Произошла ошибка при обработке запроса.\nАдминистратор уже уведомлен о проблеме. Пожалуйста, попробуйте позже или обратитесь в поддержку.",
                        reply_markup=kb
                    )
                except Exception as user_notify_error:
                    logging.error(f"Failed to send error notification to user: {user_notify_error}")
            
            # Пробрасываем исключение дальше для логирования
            raise 