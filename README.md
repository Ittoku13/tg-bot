# tg-bot

Telegram-бот для группы: игра «Олег дня», мок-ответы, скачивание YouTube/Instagram видео, мини-апп админка.

## Локальный запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # заполнить BOT_TOKEN и т.д.
python -m bot
```

Мини-апп локально: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` и туннель на порт 8080.

## Деплой на VPS

1. DNS: запись A домена `WEBAPP_DOMAIN` → IP VPS.
2. `git clone`, `cp .env.example .env`, заполнить `BOT_TOKEN`, `SUPERADMIN_ID`, `CHAT_ID`, `WEBAPP_DOMAIN`.
3. `docker compose up -d` (опционально `--profile watchtower` для автообновлений).
4. @BotFather: `/setprivacy` → Disable (бот должен видеть все сообщения для ловли ссылок и мок-ответов); Bot Settings → Menu Button → URL `https://<WEBAPP_DOMAIN>`.
5. Добавить бота в группу, выдать права админа (необязательно, но рекомендуется).

## Instagram

Для приватного/возрастного контента положить `cookies.txt` (экспорт из браузера, Netscape-формат) в data-volume: `docker cp cookies.txt tg-bot-bot-1:/app/data/cookies.txt`.

## Тесты

```bash
python -m pytest tests -q
```

## Ручной чек-лист (тестовая группа)

- [ ] `/rating`, `/mystats` — отвечают, пустой рейтинг → заглушка
- [ ] Автовыбор в заданное время (или временно поставить время «через минуту»)
- [ ] Ссылка YouTube (watch, shorts, youtu.be) → видео в чате
- [ ] Ссылка Instagram reel → видео в чате
- [ ] Мок-ответ на сообщение (поставить `mock_chance=100`)
- [ ] Режим targets: реагирует только на выбранных
- [ ] `/character`, `/admin` — только для админов
- [ ] Мини-апп: сохранение настроек, сброс рейтинга
