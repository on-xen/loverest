from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from ..states.states import CustomStarsAmount, DonationComment
from ..keyboards.inline import get_stars_payment_kb
from ..models.base import async_session
from ..models.models import User, Donation
import os

router = Router()

# Админский ID из переменных окружения
ADMIN_ID = int(os.getenv("ADMIN_ID", "5385155120"))

# Ссылка на Boosty
BOOSTY_URL = os.getenv("BOOSTY_URL")

def payment_keyboard():
    """Создает инлайн-клавиатуру с кнопкой оплаты"""
    kb = [[InlineKeyboardButton(text="Оплатить ⭐️", pay=True)]]
    
    # Добавляем кнопку Boosty, если есть ссылка
    if BOOSTY_URL:
        kb.append([InlineKeyboardButton(text="🔥 Поддержать на Boosty", url=BOOSTY_URL)])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.message(F.text == "🌟 Поддержать")
async def support_start(message: Message):
    await message.answer(
        "Ваша поддержка необходима для поддержания бота в рабочем состоянии и оплаты хостинга!\n\n"
        "Выберите количество звезд для поддержки проекта:",
        reply_markup=get_stars_payment_kb()
    )

@router.callback_query(F.data.startswith("stars_payment:"))
async def process_stars_payment(callback: CallbackQuery, state: FSMContext):
    amount = callback.data.split(":")[1]
    
    if amount == "custom":
        await state.set_state(CustomStarsAmount.waiting_for_amount)
        await callback.answer()
        await callback.message.answer("Введите желаемое количество звезд (от 1 до 100000):")
        return
    
    amount = int(amount)
    await state.update_data(amount=amount)
    # Запрашиваем комментарий
    await state.set_state(DonationComment.waiting_for_comment)
    await callback.answer()
    
    kb = [[InlineKeyboardButton(text="Пропустить", callback_data="skip_comment")]]
    await callback.message.answer(
        "Напишите комментарий к пожертвованию (или нажмите 'Пропустить'):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@router.message(CustomStarsAmount.waiting_for_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    # Проверяем введенное число
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите только число!")
        return
    
    amount = int(message.text)
    # Ограничение на сумму в Telegram
    if amount > 100000:
        await message.answer("Максимальная сумма для пожертвования - 100000 звезд.")
        return
    
    # Сохраняем сумму и запрашиваем комментарий
    await state.update_data(amount=amount)
    await state.set_state(DonationComment.waiting_for_comment)
    
    kb = [[InlineKeyboardButton(text="Пропустить", callback_data="skip_comment")]]
    await message.answer(
        "Напишите комментарий к пожертвованию (или нажмите 'Пропустить'):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@router.callback_query(F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 0)
    
    # Отправляем счет без комментария
    await state.update_data(comment=None)
    await state.clear()
    await send_invoice(callback.message, amount)
    await callback.answer()

@router.message(DonationComment.waiting_for_comment)
async def process_donation_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 0)
    
    # Сохраняем комментарий
    await state.update_data(comment=message.text)
    comment = message.text
    await state.clear()
    
    # Отправляем счет с комментарием
    await send_invoice(message, amount, comment)

async def send_invoice(message: Message, amount: int, comment: str = None):
    """Отправляет счет на оплату через Telegram Stars"""
    try:
        # Проверяем, что сумма валидная для платежной системы
        if amount <= 0 or amount > 100000:
            await message.answer("Ошибка: сумма должна быть от 1 до 100000 звезд.")
            return
            
        prices = [LabeledPrice(label="XTR", amount=amount)]
        
        # Сохраняем комментарий в payload, чтобы получить его после успешной оплаты
        payload = f"donation_{amount}"
        if comment:
            # Лимитируем длину комментария для payload (чтобы не превысить лимит)
            short_comment = comment[:50] + "..." if len(comment) > 50 else comment
            payload = f"donation_{amount}_{short_comment}"
        
        await message.answer_invoice(
            title="Поддержка Love Restaurant",
            description=f"Поддержать разработчика на {amount} звезд",
            prices=prices,
            provider_token="",  # Для Telegram Stars пустая строка
            payload=payload,
            currency="XTR",
            reply_markup=payment_keyboard(),
            provider_data='{"customTitle": "ПОДДЕРЖАТЬ"}'  # JSON строка, а не словарь
        )
    except Exception as e:
        error_message = f"Ошибка при создании счета: {e}"
        await message.answer("Произошла ошибка при создании счета. Попробуйте позже или введите другую сумму.")
        
        # Отправляем уведомление администратору о проблеме
        bot = message.bot
        admin_error_msg = (
            f"❌ Ошибка платежа!\n\n"
            f"Пользователь: {message.from_user.full_name} (ID: {message.from_user.id})\n"
            f"Сумма: {amount}\n"
            f"Ошибка: {str(e)}"
        )
        
        try:
            await bot.send_message(ADMIN_ID, admin_error_msg)
        except Exception as admin_error:
            print(f"Не удалось отправить сообщение об ошибке администратору: {admin_error}")

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Обработчик проверки перед оплатой"""
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def success_payment_handler(message: Message):
    """Обработчик успешного платежа"""
    payment = message.successful_payment
    amount = payment.total_amount
    payload = payment.invoice_payload
    
    # Извлекаем комментарий из payload, если он есть
    comment = None
    if "_" in payload and len(payload.split("_")) > 2:
        parts = payload.split("_")
        # Пропускаем первые две части (donation и amount)
        comment = "_".join(parts[2:])
    
    # Отправляем уведомление пользователю
    await message.answer(
        "🙏 Спасибо за поддержку! Ваше пожертвование поможет нам сделать бот еще лучше."
    )
    
    # Пытаемся сохранить информацию о пожертвовании в БД
    try:
        async with async_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = result.scalar_one_or_none()
            
            # Если пользователя нет, создаем его
            if not user:
                user = User(telegram_id=message.from_user.id)
                session.add(user)
                await session.flush()  # Получаем ID пользователя
            
            donation = Donation(
                user_id=user.id,
                amount=amount,
                comment=comment
            )
            session.add(donation)
            await session.commit()
    except Exception as e:
        print(f"Ошибка при сохранении пожертвования: {e}")
        # Не прерываем выполнение, даже если произошла ошибка с БД
    
    # Формируем информацию о пользователе
    user_info = f"{message.from_user.full_name}"
    if message.from_user.username:
        user_info += f" (@{message.from_user.username})"
    
    # Создаем ссылку на профиль
    user_profile_link = f"tg://user?id={message.from_user.id}"
    
    # Отправляем уведомление администратору
    admin_message = (
        f"🌟 Новое пожертвование!\n\n"
        f"От: {user_info}\n"
        f"ID: {message.from_user.id}\n"
        f"Профиль: [Открыть]({user_profile_link})\n"
        f"Сумма: {amount} звезд\n"
    )
    
    if comment:
        admin_message += f"Комментарий: {comment}\n"
        
    admin_message += f"Платеж ID: {payment.telegram_payment_charge_id}"
    
    try:
        bot = message.bot
        await bot.send_message(ADMIN_ID, admin_message, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        print(f"Ошибка при отправке уведомления администратору: {e}")

@router.message(Command("paysupport"))
async def pay_support_handler(message: Message):
    """Обработчик команды /paysupport для информации о возврате средств"""
    await message.answer(
        "Добровольные пожертвования не подразумевают возврат средств, "
        "однако, если вы столкнулись с проблемами при оплате или "
        "хотите запросить возврат - свяжитесь с администратором."
    )

@router.message(Command("donate"))
async def donate_command(message: Message):
    """Обработчик команды /donate для быстрого пожертвования"""
    await support_start(message) 