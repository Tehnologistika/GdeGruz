# 🔍 Инструкция: Как найти бота на сервере

## Вариант 1: Быстрый поиск через скрипт

```bash
# Подключитесь к серверу
ssh user@your-server-ip

# Скачайте скрипт поиска
curl -O https://raw.githubusercontent.com/Tehnologistika/GdeGruz/claude/document-management-system-011CUmN9GrnFqDZYHjmTdALk/find_bot.sh
chmod +x find_bot.sh

# Запустите поиск
./find_bot.sh
```

Пришлите мне вывод этой команды!

---

## Вариант 2: Ручной поиск

### Шаг 1: Подключитесь к серверу

```bash
# Если у вас новый ключ SSH
ssh -i /path/to/new/key user@server-ip

# Или просто
ssh user@server-ip
```

### Шаг 2: Проверьте запущенные Docker контейнеры

```bash
docker ps -a
```

**Ищите контейнеры с названиями:**
- `fleet-live-bot_bot_1`
- `fleet-live-bot-bot-1`
- или что-то похожее на `gdegruz`, `bot`

### Шаг 3: Найдите папку с проектом

```bash
# Поиск в /home
find /home -type d -name "*fleet*" 2>/dev/null
find /home -type d -name "*bot*" 2>/dev/null

# Поиск docker-compose.yml
find /home -name "docker-compose.yml" 2>/dev/null

# Поиск по git репозиториям
find /home -type d -name ".git" 2>/dev/null
```

### Шаг 4: Проверьте типичные расположения

```bash
# Проверьте эти папки по очереди:
ls -la /home/git/fleet-live-bot/
ls -la /home/ubuntu/fleet-live-bot/
ls -la /opt/fleet-live-bot/
ls -la /root/fleet-live-bot/
ls -la ~/fleet-live-bot/
```

### Шаг 5: Найдите через процессы Python

```bash
# Найти запущенные Python процессы
ps aux | grep python
ps aux | grep aiogram
ps aux | grep bot
```

### Шаг 6: Проверьте все пользователи

```bash
# Посмотрите всех пользователей
cat /etc/passwd | grep -v nologin | grep -v false

# Проверьте их домашние папки
ls -la /home/
```

---

## Вариант 3: Через Git репозиторий

Если вы помните адрес Git репозитория:

```bash
# Клонируйте заново в новое место
cd ~
git clone https://github.com/Tehnologistika/GdeGruz.git fleet-live-bot
cd fleet-live-bot

# Переключитесь на ветку с документами
git checkout claude/document-management-system-011CUmN9GrnFqDZYHjmTdALk

# Скопируйте .env из старого места или создайте новый
cp /path/to/old/.env .env
# ИЛИ создайте новый из примера
cp .env.example .env
nano .env  # настройте переменные
```

---

## Что делать, если нашли папку

### 1. Зайдите в папку
```bash
cd /path/to/fleet-live-bot
```

### 2. Проверьте git статус
```bash
git status
git branch -a
```

### 3. Обновите код
```bash
git fetch origin
git checkout claude/document-management-system-011CUmN9GrnFqDZYHjmTdALk
git pull origin claude/document-management-system-011CUmN9GrnFqDZYHjmTdALk
```

### 4. Проверьте .env
```bash
cat .env | grep -v "TOKEN\|SECRET"
```

### 5. Добавьте ID группы документов
```bash
echo "" >> .env
echo "DOCUMENTS_GROUP_ID=-5054329274" >> .env
```

### 6. Перезапустите бота
```bash
docker compose down
docker compose up -d --build
docker logs -f fleet-live-bot_bot_1
```

---

## Частые проблемы

### Проблема: "Permission denied" при подключении SSH

```bash
# Установите правильные права на новый ключ
chmod 600 /path/to/new/ssh/key

# Подключитесь с явным указанием ключа
ssh -i /path/to/new/ssh/key user@server-ip
```

### Проблема: Не знаю IP сервера

Проверьте:
- Панель управления хостинга (Digital Ocean, AWS, etc.)
- Старые SSH конфигурации: `cat ~/.ssh/config`
- История команд: `history | grep ssh`
- Email от хостинга

### Проблема: Не знаю пользователя

Типичные пользователи:
- `root`
- `ubuntu`
- `git`
- `admin`
- `deploy`

Попробуйте:
```bash
ssh root@server-ip
ssh ubuntu@server-ip
ssh git@server-ip
```

---

## Если ничего не нашли - разверните заново

### 1. Создайте свежую установку

```bash
# Подключитесь к серверу
ssh user@server-ip

# Клонируйте репозиторий
cd /home/git  # или другая подходящая папка
git clone https://github.com/Tehnologistika/GdeGruz.git fleet-live-bot
cd fleet-live-bot

# Переключитесь на нужную ветку
git checkout claude/document-management-system-011CUmN9GrnFqDZYHjmTdALk
```

### 2. Настройте .env

```bash
cp .env.example .env
nano .env
```

Заполните:
```env
BOT_TOKEN=ваш_токен_бота
ADMIN_ID=ваш_telegram_id
GROUP_CHAT_ID=id_группы_курьеров
DOCUMENTS_GROUP_ID=-5054329274
REMIND_HOURS=0.2
TIMEZONE=Europe/Berlin
```

### 3. Запустите

```bash
docker compose up -d --build
docker logs -f fleet-live-bot_bot_1
```

---

## Нужна помощь?

Пришлите мне:

1. **Вывод команды** `./find_bot.sh`
2. **Или вывод этих команд:**
   ```bash
   docker ps -a
   find /home -name "docker-compose.yml"
   ls -la /home/
   ```
3. **Информацию о хостинге:** где размещен сервер (AWS, Digital Ocean, etc.)

Я помогу найти бота!
