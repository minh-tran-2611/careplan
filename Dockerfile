FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0

WORKDIR /app
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt

COPY . .
RUN useradd --create-home app && chown -R app:app /app
USER app

EXPOSE 8000
# Render cấp cổng qua biến PORT; --proxy-headers để nhận đúng https và IP người dùng sau proxy của Render.
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
