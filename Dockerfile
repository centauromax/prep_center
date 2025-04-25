# ---- Fase runtime unica ----------------------------------------------------
FROM python:3.11-slim

# Evita byte-code, log su stdout
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dipendenze di sistema minime per psycopg2-binary e gunicorn
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Installa requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il resto del progetto
COPY . .

# Cartella log richiesta in settings.py
RUN mkdir -p /var/www/html/logs && chmod 777 /var/www/html/logs

EXPOSE 8000

CMD python manage.py migrate && \
    python manage.py collectstatic --noinput && \
    gunicorn prep_center.wsgi --bind 0.0.0.0:${PORT:-8000} 