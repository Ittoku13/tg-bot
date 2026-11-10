# tg-bot

Telegram-бот для группы: игра «Олег дня», мок-ответы, скачивание YouTube/Instagram видео, мини-апп админка.

## Установка на сервер (VPS)

Требования: установленные Docker и Docker Compose, домен, направленный на IP сервера (запись A).

```bash
git clone https://github.com/Ittoku13/tg-bot.git
cd tg-bot
cp .env.example .env
```

Заполнить `.env`:

```text
BOT_TOKEN=        # токен от @BotFather
SUPERADMIN_ID=    # твой numeric user id (узнать: @userinfobot)
CHAT_ID=          # id группы (отрицательное число; узнать: @getmyid_bot)
WEBAPP_DOMAIN=    # домен мини-аппа, например admin.example.com
```

Запуск:

```bash
docker compose up -d
```

Caddy сам получит TLS-сертификат для `WEBAPP_DOMAIN`.

## Настройка Telegram

1. @BotFather → `/setprivacy` → **Disable** (бот должен видеть все сообщения для ловли ссылок и мок-ответов).
2. @BotFather → Bot Settings → Menu Button → URL `https://<WEBAPP_DOMAIN>`.
3. Добавить бота в группу, выдать права админа (необязательно, но рекомендуется).

## Instagram

Для приватного/возрастного контента положить `cookies.txt` (экспорт из браузера, Netscape-формат) в data-volume:

```bash
docker cp cookies.txt $(docker compose ps -q bot):/app/data/cookies.txt
```

## Команды

- `/rating` — рейтинг с переключателем периода (всё время / месяц / неделя)
- `/mystats` — личная статистика
- `/character` — смена характера бота (админы)
- `/admin` — открыть админку (мини-апп, только админы)
