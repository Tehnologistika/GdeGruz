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

## Docker Setup

### Quick Start

Run the automated setup script:

```bash
./start-docker.sh
```

This script will:
- Check Docker installation
- Start Docker daemon if needed
- Create .env file from backup
- Start all containers

### Manual Setup

If you prefer manual setup:

1. **Install Docker** (if not already installed):
```bash
apt-get update
apt-get install -y docker.io docker-compose-v2
```

2. **Configure Docker daemon** (create `/etc/docker/daemon.json`):
```json
{
  "storage-driver": "vfs",
  "iptables": false,
  "ip6tables": false,
  "bridge": "none"
}
```

3. **Start Docker daemon**:
```bash
dockerd > /var/log/docker.log 2>&1 &
```

4. **Create .env file**:
```bash
cp .env.bak.2025-10-09-065813 .env
# Or create new .env with required variables:
# API_SECRET_TOKEN=your_token_here
# DAILY_REMIND=1
# REMIND_AT=09:30
# TIMEZONE=Europe/Berlin
```

5. **Start containers**:
```bash
docker compose up -d
```

### Docker Commands

- View running containers: `docker compose ps`
- View logs: `docker compose logs -f`
- View specific service logs: `docker compose logs -f bot` or `docker compose logs -f web`
- Stop containers: `docker compose down`
- Rebuild containers: `docker compose up -d --build`
- Restart containers: `docker compose restart`

### Troubleshooting

**Docker daemon not starting:**
- Check logs: `cat /var/log/docker.log`
- Ensure Docker is installed: `docker --version`
- Verify daemon config: `cat /etc/docker/daemon.json`

**403 Forbidden when pulling images:**
- This indicates Docker Hub rate limiting or network restrictions
- Try using a Docker registry mirror
- Contact your network administrator

**Containers not starting:**
- Check logs: `docker compose logs`
- Verify .env file exists and contains correct values
- Ensure ports 8000 is not in use: `netstat -tlnp | grep 8000`

## Usage

1. `/start` — приветствие.
2. Нажимать кнопку раз в 24 ч.
3. Live Location идёт автоматически.
4. Бот напоминает, если водитель забыл.

