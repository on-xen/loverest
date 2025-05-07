# PowerShell скрипт для сброса базы данных

Write-Host "⚠️ WARNING! This will delete all data in the database! ⚠️" -ForegroundColor Red
$answer = Read-Host -Prompt "Are you sure you want to continue? (yes/no)"

if ($answer -ne "yes" -and $answer -ne "y") {
    Write-Host "Operation cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host "Resetting database..." -ForegroundColor Cyan

# Останавливаем контейнер с ботом
docker-compose stop bot

# Удаляем схему и создаем ее заново
docker exec loverest-postgres-1 bash -c "PGPASSWORD=password psql -U user -d love_restaurant -c 'DROP SCHEMA public CASCADE;'"
docker exec loverest-postgres-1 bash -c "PGPASSWORD=password psql -U user -d love_restaurant -c 'CREATE SCHEMA public;'"

# Перезапускаем контейнер с миграциями для создания структуры БД заново
docker-compose up -d --force-recreate migrations

# Ждем, пока миграции выполнятся
Start-Sleep -Seconds 5

# Запускаем бота снова
docker-compose up -d bot

Write-Host "✅ Database has been reset successfully!" -ForegroundColor Green 