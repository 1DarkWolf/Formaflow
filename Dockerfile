FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

RUN addgroup --system formaflow && adduser --system --ingroup formaflow formaflow

COPY requirements/ requirements/
RUN python -m pip install --no-cache-dir -r requirements/production.txt

COPY --chown=formaflow:formaflow . .
RUN chmod 755 scripts/entrypoint.sh \
    && mkdir -p /data/private_uploads /app/staticfiles \
    && chown -R formaflow:formaflow /data/private_uploads /app/staticfiles \
    && DJANGO_SETTINGS_MODULE=config.settings.build python manage.py collectstatic --noinput

USER formaflow

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
