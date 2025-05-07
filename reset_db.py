import os
import sys
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from bot.models.base import Base, engine, async_session
from bot.models.models import User, Restaurant, MenuItem, Order, OrderItem
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_database():
    """Удаляет и пересоздает базу данных"""
    try:
        # Удаляем все таблицы
        logger.info("Dropping all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        # Создаем таблицы заново
        logger.info("Creating all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database has been reset successfully!")
        
        # Создаем тестового администратора
        async with async_session() as session:
            # Проверяем существует ли админ
            admin_id = int(os.getenv("ADMIN_ID", "5385155120"))
            admin = User(
                telegram_id=admin_id,
                is_restaurant_owner=True,
                created_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc)
            )
            session.add(admin)
            await session.commit()
            
            logger.info(f"Created admin user with ID: {admin_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        return False

if __name__ == "__main__":
    print("⚠️ WARNING! This will delete all data in the database! ⚠️")
    answer = input("Are you sure you want to continue? (yes/no): ")
    
    if answer.lower() not in ("yes", "y"):
        print("Operation cancelled.")
        sys.exit(0)
    
    print("Resetting database...")
    result = asyncio.run(reset_database())
    
    if result:
        print("✅ Database has been reset successfully!")
    else:
        print("❌ Failed to reset database. Check the logs for details.") 