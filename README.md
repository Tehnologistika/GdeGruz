# GdeGruz

This repository outlines a minimal setup for a Telegram bot built with **Aiogram 3** alongside a **FastAPI** web API. The project demonstrates persistence using **SQLite**, containerization with **Docker** and **docker-compose**, and a GitHub Actions workflow for deployment.

## Project tree

```text
.
├── bot/
│   └── main.py
├── web/
│   └── api.py
├── templates/
│   └── map.html
├── nginx/
│   └── bot.conf
├── db.py
├── deploy.sh
├── Dockerfile
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── deploy.yml
├── requirements.txt
└── README.md
```

## requirements.txt

```text
aiogram==3.0.0
fastapi==0.103.1       # совместима с typing-extensions 4.7.*
aiosqlite==0.19.0
python-dotenv==1.0.1
uvicorn==0.29.0
jinja2==3.1.3
```

## Usage

1. `/start` — приветствие.
2. Нажимать кнопку раз в 24 ч.
3. Live Location идёт автоматически.
4. Бот напоминает, если водитель забыл.

