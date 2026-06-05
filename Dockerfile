FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Fly sets PORT env var; gunicorn binds to it
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 60
