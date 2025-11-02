#!/bin/bash

# Script to start Docker daemon and run docker compose
# This script handles Docker daemon startup in environments without systemd

set -e

echo "🚀 Starting Docker setup..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if Docker daemon is running
check_docker_daemon() {
    docker info &> /dev/null
    return $?
}

# Function to start Docker daemon
start_docker_daemon() {
    echo -e "${YELLOW}Starting Docker daemon...${NC}"

    # Create Docker config directory if it doesn't exist
    mkdir -p /etc/docker

    # Check if daemon.json exists
    if [ ! -f /etc/docker/daemon.json ]; then
        echo -e "${YELLOW}Creating Docker daemon config...${NC}"
        cat > /etc/docker/daemon.json <<EOF
{
  "storage-driver": "vfs",
  "iptables": false,
  "ip6tables": false,
  "bridge": "none"
}
EOF
    fi

    # Kill any existing dockerd processes
    pkill -9 dockerd 2>/dev/null || true

    # Start dockerd in background
    dockerd > /var/log/docker.log 2>&1 &

    # Wait for daemon to be ready (max 30 seconds)
    echo -e "${YELLOW}Waiting for Docker daemon to be ready...${NC}"
    for i in {1..30}; do
        if check_docker_daemon; then
            echo -e "${GREEN}✓ Docker daemon is ready${NC}"
            return 0
        fi
        sleep 1
    done

    echo -e "${RED}✗ Docker daemon failed to start${NC}"
    echo "Check logs at: /var/log/docker.log"
    return 1
}

# Function to check .env file
check_env_file() {
    if [ ! -f .env ]; then
        if [ -f .env.bak.2025-10-09-065813 ]; then
            echo -e "${YELLOW}Creating .env from backup...${NC}"
            cp .env.bak.2025-10-09-065813 .env
            echo -e "${GREEN}✓ .env file created${NC}"
        else
            echo -e "${RED}✗ .env file not found${NC}"
            echo "Please create .env file with required variables"
            return 1
        fi
    else
        echo -e "${GREEN}✓ .env file exists${NC}"
    fi
}

# Main execution
main() {
    cd /home/user/GdeGruz || exit 1

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker is not installed${NC}"
        echo "Please run: apt-get install -y docker.io docker-compose-v2"
        exit 1
    fi

    # Check and start Docker daemon if needed
    if ! check_docker_daemon; then
        start_docker_daemon || exit 1
    else
        echo -e "${GREEN}✓ Docker daemon is already running${NC}"
    fi

    # Check .env file
    check_env_file || exit 1

    # Run docker compose
    echo -e "${YELLOW}Starting containers with docker compose...${NC}"
    if docker compose up -d; then
        echo -e "${GREEN}✓ Containers started successfully${NC}"
        echo ""
        echo "View container status: docker compose ps"
        echo "View logs: docker compose logs -f"
        echo "Stop containers: docker compose down"
    else
        echo -e "${RED}✗ Failed to start containers${NC}"
        echo ""
        echo "Common issues:"
        echo "1. Docker Hub rate limit or network issues"
        echo "   - Try again later or configure Docker registry mirror"
        echo "2. Missing dependencies"
        echo "   - Check docker-compose.yml and Dockerfile"
        echo ""
        echo "Check logs: docker compose logs"
        exit 1
    fi
}

# Run main function
main
