# Use Python 3.12 slim image as the base for building dependencies
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy the rest of the application source code
COPY . .

# ------------------------
# Final runtime stage
# ------------------------
FROM python:3.12-slim AS runtime

# Copy installed Python packages from the builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Set workdir and copy application source
WORKDIR /app
COPY --from=builder /app /app

# Default environment variables
ENV STAGE=bot \
    PYTHONUNBUFFERED=1

# Run bot or web depending on STAGE variable
CMD if [ "$STAGE" = "bot" ]; then \
        python -m bot.main; \
    elif [ "$STAGE" = "web" ]; then \
        uvicorn web.api:app --host 0.0.0.0 --port 8000; \
    else \
        echo "Unknown STAGE: $STAGE" && exit 1; \
    fi
