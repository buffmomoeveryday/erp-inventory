FROM python:3.14-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=core.settings

RUN chmod +x docker-entrypoint.sh \
    && mkdir -p /data \
    && SQLITE_DB_PATH=/tmp/build.sqlite DEBUG=False USE_WHITENOISE=1 \
       DJANGO_SECRET_KEY=collectstatic-build-only ALLOWED_HOSTS=localhost \
       python manage.py collectstatic --noinput \
    && rm -f /tmp/build.sqlite

EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]
