# Auksjonen.no - Skoda Superb Monitor

Telegram-бот, який моніторить auksjonen.no і надсилає сповіщення коли з'являється Skoda Superb.

---

## Крок 1 - Створити Telegram бота

1. Відкрий Telegram, знайди **@BotFather**
2. Надішли `/newbot`
3. Придумай назву (наприклад: `Auksjonen Monitor`)
4. Придумай username (наприклад: `auksjonen_skoda_bot`) - має закінчуватись на `bot`
5. BotFather надішле **токен** - виглядає так: `7123456789:AAFxxxxxxxxxxxxxxxx` - збережи його

6. Знайди свого нового бота в Telegram і надішли йому будь-яке повідомлення (наприклад "hi")
7. Відкрий у браузері (підстав свій токен):
   ```
   https://api.telegram.org/bot<ТВІЙ_ТОКЕН>/getUpdates
   ```
8. В відповіді знайди `"chat":{"id":ЧИСЛО}` - це твій **chat_id**

---

## Крок 2 - Задеплоїти на Railway (безкоштовно)

### 2.1 - Завантаж файли на GitHub
1. Створи акаунт на https://github.com (якщо нема)
2. Створи новий **приватний** репозиторій (New repository → Private)
3. Завантаж 3 файли: `monitor.py`, `requirements.txt`, `Procfile`
   - Натисни "uploading an existing file" і перетягни всі три

### 2.2 - Підключи Railway
1. Зайди на https://railway.app
2. Натисни **"Start a New Project"** → **"Deploy from GitHub repo"**
3. Авторизуй GitHub і вибери свій репозиторій
4. Railway автоматично виявить `Procfile` і запустить `worker`

### 2.3 - Додай змінні середовища
В Railway, у своєму проекті:
1. Перейди у вкладку **Variables**
2. Додай дві змінні:
   - `TELEGRAM_TOKEN` = `7123456789:AAFxxxxxxxxxxxxxxxx` (твій токен від BotFather)
   - `TELEGRAM_CHAT_ID` = `123456789` (твій chat id)
3. Railway автоматично перезапустить сервіс

Після цього бот надішле тобі повідомлення: **"✅ Монітор запущено!"**

---

## Зміна інтервалу перевірки

В файлі `monitor.py`, рядок 13:
```python
CHECK_INTERVAL_MINUTES = 30  # змінити на потрібну кількість хвилин
```
Після зміни - просто запушити у GitHub, Railway автоматично перезапустить.

---

## Зміна пошукового запиту

В `monitor.py`, рядок 15:
```python
KEYWORDS = ["superb"]  # можна додати більше: ["superb", "octavia"]
```

---

## Безкоштовний план Railway

Railway дає ~$5 кредитів на місяць безкоштовно. Цей скрипт використовує мінімум ресурсів (просто спить більшість часу), тому кредитів вистачить надовго - зазвичай на кілька місяців.
