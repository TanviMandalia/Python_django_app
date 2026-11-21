FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=myproject.settings.production

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . ./

# Static collection needs production settings to load, but must not connect to
# a live database or bake deployment credentials into the image.
RUN DATABASE_URL=postgresql://build:build@127.0.0.1:5432/build \
    DJANGO_SECRET_KEY=build-only-not-a-runtime-secret \
    python manage.py collectstatic --no-input --settings=myproject.settings.production

EXPOSE 8080

# Cloud Run injects PORT. One worker keeps the default instance memory modest;
# increase only after measuring the service under real traffic.
CMD ["sh", "-c", "gunicorn myproject.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --timeout 120"]
