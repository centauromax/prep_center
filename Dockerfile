# Usa l'immagine Python ufficiale
FROM python:3.11-slim

WORKDIR /app

# Installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'applicazione
COPY . .

# Imposta le variabili d'ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Espone la porta su cui sarà in ascolto l'app
EXPOSE 8000

# Comandi che verranno eseguiti al lancio del container
CMD python manage.py migrate && \
    python manage.py collectstatic --noinput && \
    gunicorn prep_center.wsgi --bind 0.0.0.0:$PORT 