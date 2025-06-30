# GdeGruz

This repository outlines a minimal setup for a Telegram bot built with **Aiogram 3** alongside a **FastAPI** web API. The project demonstrates persistence using **SQLite**, containerization with **Docker** and **docker-compose**, and a GitHub Actions workflow for deployment.

## Project tree

```text
app/
├── bot/
│   └── main.py
├── api/
│   ├── main.py
│   └── templates/
│       └── index.html
├── db.py
Dockerfile
docker-compose.yml
.github/
└── workflows/
    └── deploy.yml
requirements.txt
README.md
```

## requirements.txt

```text
aiogram==3.0.0
fastapi==0.110.0
uvicorn==0.29.0
aiosqlite==0.19.0
jinja2==3.1.3
python-dotenv==1.0.1
```
