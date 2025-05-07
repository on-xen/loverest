# Love Restaurant Bot

Telegram бот для создания виртуальных ресторанов любви, где можно "оплачивать" блюда поцелуями и обнимашками.

## Функционал

- Создание ресторана с уникальным кодом приглашения
- Добавление позиций в меню с фото, описанием и "ценой" в поцелуях или обнимашках
- Подключение к ресторану по коду или ссылке
- Оформление заказов с корзиной
- Уведомления владельцу ресторана о новых заказах
- Система поддержки через Telegram Stars и Boosty

## Установка и запуск

### Необходимые компоненты

- Docker и Docker Compose
- Telegram Bot Token (получить у @BotFather)

### Установка с помощью скриптов

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/love-restaurant-bot.git
cd love-restaurant-bot
```

2. Запустите скрипт установки:

**Linux/macOS:**
```bash
chmod +x install.sh
./install.sh
```

**Windows:**
```powershell
# Запустите PowerShell от имени администратора
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
./install.ps1
```

Скрипт автоматически создаст файл .env с необходимыми настройками и запустит контейнеры.

## Команды бота

- `/start` - Начать работу с ботом
- `/paysupport` - Информация о возврате средств
- `/donate` - Быстрое пожертвование

## Технологии

- Python 3.11
- aiogram 3.20+
- PostgreSQL + SQLAlchemy (ORM с асинхронным режимом)
- Redis (хранение состояний FSM)
- Docker + Docker Compose
- Alembic (миграции базы данных)
- XTR API (для оплаты Telegram Stars) 