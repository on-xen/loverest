#!/bin/bash

echo "⚠️ WARNING! This will delete all data in the database! ⚠️"
read -p "Are you sure you want to continue? (yes/no): " answer

if [[ "$answer" != "yes" && "$answer" != "y" ]]; then
    echo "Operation cancelled."
    exit 0
fi

echo "Resetting database..."

# Удаляем схему и создаем ее заново
docker exec loverest-postgres-1 bash -c 'PGPASSWORD=password psql -U user -d love_restaurant -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'

# Перезапускаем контейнер с миграциями для создания структуры БД заново
docker-compose up -d --force-recreate migrations

echo "✅ Database has been reset successfully!" 