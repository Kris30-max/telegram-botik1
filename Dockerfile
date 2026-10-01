FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 app
USER app

# Миграции перед стартом: Railway config-as-code (preDeployCommand) для сервиса недоступен.
CMD ["sh", "-c", "alembic upgrade head && exec python -m bot.main"]
