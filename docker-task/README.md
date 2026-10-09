# Docker task: API + PostgreSQL

Два контейнера в одной сети:
- `db`  - PostgreSQL 16, данные в named volume `pgdata`
- `api` - Flask-приложение (точка входа), порт 8080

## Docker Hub
- https://hub.docker.com/r/nikitaku1/task-api
- https://hub.docker.com/r/nikitaku1/task-db

## Запуск
    cp .env.example .env
    docker compose up -d --build

## Тестирование
    curl http://localhost:8080/health
    curl http://localhost:8080/items
    curl -X POST http://localhost:8080/items -H "Content-Type: application/json" -d '{"name":"test"}'

## Проверка сохранности данных
    docker compose down       # без -v
    docker compose up -d
    curl http://localhost:8080/items   # данные на месте

## Остановка
    docker compose down       # данные сохраняются
    docker compose down -v    # ВНИМАНИЕ: удаляет данные
