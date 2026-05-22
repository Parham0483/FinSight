FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2 + cryptography + statsmodels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying code (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user for security
RUN useradd -m -u 1000 finsight && chown -R finsight:finsight /app
USER finsight

EXPOSE 8000
