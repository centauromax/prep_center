# Usa un'immagine Python ufficiale
FROM python:3.12

# Imposta variabili d'ambiente per prevenire la scrittura di file .pyc e per il buffering
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Crea un gruppo e un utente non-root
RUN groupadd --system appgroup && useradd --system --gid appgroup --no-create-home appuser

# Crea la directory per i log temporanei (come da settings.py) e imposta i permessi
# Assicurati che /tmp esista e sia scrivibile, il che di solito è vero.
# La directory LOG_DIR è /tmp/logs
RUN mkdir -p /tmp/logs && \
    chown -R appuser:appgroup /tmp/logs && \
    chmod -R 755 /tmp/logs

# Imposta la directory di lavoro nell'immagine
WORKDIR /app

# Copia prima il file delle dipendenze per sfruttare il caching di Docker
COPY requirements.txt .

# Installa le dipendenze di sistema se necessario (es. per psycopg2 o altre librerie)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia il file di configurazione di Gunicorn dalla root del progetto (relativo al contesto di build backend/)
COPY ../gunicorn.conf.py gunicorn.conf.py

# Copia il resto del codice dell'applicazione dalla directory backend locale alla directory /app nell'immagine
COPY . .

# Cambia il proprietario di tutti i file dell'applicazione all'utente appuser
# Questo assicura che l'utente non-root possa eseguire e potenzialmente scrivere (se necessario per media, static temporanei, ecc.)
RUN chown -R appuser:appgroup /app
RUN chmod -R 755 /app # Assicura che i file siano eseguibili/leggibili

# Passa all'utente non-root
# USER appuser

# Il Procfile si occuperà di eseguire i comandi specifici (runserver, celery worker)
# Quindi non abbiamo bisogno di un CMD o ENTRYPOINT qui se il Procfile è il punto di ingresso principale per Railway.
# Se Railway richiedesse un CMD/ENTRYPOINT di fallback, potremmo aggiungerne uno. 