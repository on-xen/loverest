import asyncio
import logging
import signal
import sys
import atexit
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import os
from dotenv import load_dotenv

from .handlers import start, restaurant_owner, partner, payments, admin, broadcasts
from .middlewares import AntiSpamMiddleware, ErrorMonitorMiddleware

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logging.critical("No BOT_TOKEN provided in environment variables")
    sys.exit(1)

# Admin ID
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    if ADMIN_ID == 0:
        logging.warning("No ADMIN_ID provided in environment variables, admin notifications will be disabled")
except ValueError:
    logging.error("Invalid ADMIN_ID provided, must be an integer")
    ADMIN_ID = 0

# Bot instance (global for signal handlers)
bot = None
shutdown_event = asyncio.Event()

async def on_shutdown(signal_type=None):
    """Send notification to admin when bot is shutting down"""
    if bot and ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID, 
                f"⚠️ Бот Love Restaurant останавливается!\n"
                f"Причина: {signal_type or 'Неизвестно'}\n"
                f"Время: {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, '', 0, None, None))}"
            )
            logging.info(f"Shutdown notification sent to admin (ID: {ADMIN_ID})")
        except Exception as e:
            logging.error(f"Failed to send shutdown notification: {e}")
    
    # Set the shutdown event
    shutdown_event.set()

# Register the atexit handler for Docker container shutdown
def exit_handler():
    if sys.platform == 'win32':
        asyncio.run(on_shutdown("WINDOWS_EXIT"))
    else:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(on_shutdown("CONTAINER_SHUTDOWN"))
        else:
            asyncio.run(on_shutdown("CONTAINER_SHUTDOWN"))

atexit.register(exit_handler)

async def main():
    global bot
    
    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register error monitoring middleware (should be first to catch all errors)
    error_monitor = ErrorMonitorMiddleware()
    dp.message.middleware(error_monitor)
    dp.callback_query.middleware(error_monitor)
    dp.inline_query.middleware(error_monitor)
    dp.chosen_inline_result.middleware(error_monitor)
    dp.edited_message.middleware(error_monitor)
    dp.channel_post.middleware(error_monitor)
    dp.edited_channel_post.middleware(error_monitor)
    dp.poll.middleware(error_monitor)
    dp.poll_answer.middleware(error_monitor)
    dp.my_chat_member.middleware(error_monitor)
    dp.chat_member.middleware(error_monitor)
    dp.chat_join_request.middleware(error_monitor)
    
    # Register anti-spam middlewares with different limits for different event types
    dp.message.middleware(AntiSpamMiddleware(rate_limit=3, time_window=3))
    dp.callback_query.middleware(AntiSpamMiddleware(rate_limit=5, time_window=3))
    
    # Register routers
    dp.include_router(start.router)
    dp.include_router(restaurant_owner.router)
    dp.include_router(partner.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)
    dp.include_router(broadcasts.router)
    
    # Инициализируем планировщик рассылок
    broadcasts.start_broadcast_scheduler(bot)
    
    # Notify admin when bot starts
    if ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID, 
                f"✅ Бот Love Restaurant запущен и готов к работе!\n"
                f"Версия: 1.2.0\n"
                f"Дата: {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, '', 0, None, None))}"
            )
            logging.info(f"Startup notification sent to admin (ID: {ADMIN_ID})")
        except Exception as e:
            logging.error(f"Failed to send startup notification: {e}")
    
    # Start polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Workaround to handle Docker container shutdown
    polling_task = asyncio.create_task(dp.start_polling(bot))
    
    # Run the bot until the shutdown event is set
    await shutdown_event.wait()
    
    # Cancel polling when shutdown is requested
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        logging.info("Polling task cancelled")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda sig, f: asyncio.create_task(on_shutdown(signal.Signals(sig).name)))
        except (ValueError, AttributeError) as e:
            logging.warning(f"Failed to set handler for {getattr(signal.Signals, str(sig), sig)}: {e}")
    
    # Add SIGHUP only for non-Windows platforms
    if sys.platform != 'win32':
        try:
            signal.signal(signal.SIGHUP, lambda sig, f: asyncio.create_task(on_shutdown(signal.Signals(sig).name)))
        except (ValueError, AttributeError) as e:
            logging.warning(f"Failed to set handler for SIGHUP: {e}")

if __name__ == "__main__":
    try:
        # Setup signal handlers regardless of platform
        setup_signal_handlers()
        
        # Run the bot
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by keyboard interrupt or system exit!")
        asyncio.run(on_shutdown("MANUAL_SHUTDOWN"))
    except Exception as e:
        logging.critical(f"Unexpected error: {e}", exc_info=True)
        asyncio.run(on_shutdown(f"ERROR: {str(e)}")) 