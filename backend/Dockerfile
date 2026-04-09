FROM python:3.11-slim

WORKDIR /app

# Install shared package first (for caching)
COPY shared/ ./shared/
RUN pip install --no-cache-dir -e ./shared

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Create prompts directory
RUN mkdir -p /app/prompts

ENV PYTHONUNBUFFERED=1

CMD ["gunicorn", "main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--workers", "2", "--bind", "0.0.0.0:8000", "--access-logfile", "-"]
