FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Cloud Run injects PORT; default to 8000 for local use)
ENV PORT=8000
EXPOSE 8000

# Run migrations, seed demo data (idempotent), then start the server on $PORT
CMD ["sh", "-c", "python -m app.utils.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
