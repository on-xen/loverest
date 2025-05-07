import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import os
import logging

class AntiSpamMiddleware(BaseMiddleware):
    """
    Middleware для защиты от спама.
    Ограничивает количество запросов от одного пользователя в определенный промежуток времени.
    """
    
    def __init__(self, rate_limit: int = 2, time_window: int = 2):
        """
        :param rate_limit: Максимальное количество запросов в заданный промежуток времени
        :param time_window: Временное окно в секундах
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.user_requests = {}  # user_id -> [timestamp1, timestamp2, ...]
        self.admin_id = int(os.getenv("ADMIN_ID", "5385155120"))
        self.spam_notifications = {}  # user_id -> last_notification_time
        self.notification_cooldown = 60  # Не отправлять уведомления чаще чем раз в минуту
        # Команды, которые исключены из ограничений спама
        self.exempt_commands = ["/start", "/help", "/cancel"]
        logging.info(f"AntiSpamMiddleware initialized with rate_limit={rate_limit}, time_window={time_window}, exempt_commands={self.exempt_commands}")
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем ID пользователя
        user_id = None
        is_command = False
        exempt_command = False
        command_text = ""
        
        if isinstance(event, Message):
            user_id = event.from_user.id
            # Проверяем, является ли сообщение командой
            if event.text and event.text.startswith('/'):
                is_command = True
                command_text = event.text.split()[0].lower()  # Извлекаем команду (первое слово)
                # Проверяем, является ли команда исключенной
                if any(command_text == cmd for cmd in self.exempt_commands):
                    exempt_command = True
                    logging.info(f"Exempt command detected: {command_text} from user {user_id}")
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        # Если не удалось определить ID пользователя, это сообщение от админа или исключенная команда, пропускаем проверку
        if not user_id or user_id == self.admin_id or exempt_command:
            return await handler(event, data)
        
        current_time = time.time()
        
        # Инициализируем список запросов, если его нет
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        # Очищаем старые запросы
        self.user_requests[user_id] = [
            timestamp for timestamp in self.user_requests[user_id]
            if current_time - timestamp < self.time_window
        ]
        
        # Проверяем, не превышает ли пользователь лимит
        if len(self.user_requests[user_id]) >= self.rate_limit:
            # Пользователь превысил лимит, блокируем запрос
            if isinstance(event, Message):
                await event.answer("🚫 Слишком много запросов. Пожалуйста, подождите несколько секунд.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Слишком много запросов. Пожалуйста, подождите.", show_alert=True)
            
            # Если это уже пятый запрос подряд слишком быстро, уведомляем администратора
            if len(self.user_requests[user_id]) >= self.rate_limit * 2.5:
                # Проверяем, не отправляли ли мы уже уведомление недавно
                should_notify = True
                if user_id in self.spam_notifications:
                    if current_time - self.spam_notifications[user_id] < self.notification_cooldown:
                        should_notify = False
                
                if should_notify:
                    bot = data.get("bot")
                    if bot:
                        try:
                            username = event.from_user.username or "Нет username"
                            full_name = event.from_user.full_name or "Неизвестный пользователь"
                            
                            # Определяем тип события
                            event_type = "сообщение"
                            event_content = ""
                            if isinstance(event, Message):
                                event_type = "сообщение"
                                if is_command:
                                    event_type = "команда"
                                event_content = f"Содержание: {event.text}"
                            elif isinstance(event, CallbackQuery):
                                event_type = "нажатие кнопки"
                                event_content = f"Callback: {event.data}"
                            
                            await bot.send_message(
                                self.admin_id,
                                f"⚠️ Обнаружен возможный спам!\n\n"
                                f"Пользователь: {full_name} (@{username})\n"
                                f"ID: {user_id}\n"
                                f"Тип: {event_type}\n"
                                f"{event_content}\n"
                                f"Количество запросов: {len(self.user_requests[user_id])} за {self.time_window} сек."
                            )
                            # Обновляем время последнего уведомления
                            self.spam_notifications[user_id] = current_time
                            logging.info(f"Spam notification sent for user {user_id}")
                        except Exception as e:
                            logging.error(f"Failed to send spam notification: {e}")
            
            return None
        
        # Добавляем текущий запрос в историю
        self.user_requests[user_id].append(current_time)
        
        # Передаем управление следующему обработчику
        return await handler(event, data) 