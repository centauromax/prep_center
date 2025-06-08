#!/bin/bash
set -e

echo "🚀 Avvio deploy backend..."

# Migrazione database
echo "📦 Esecuzione migrazioni database..."
python manage.py migrate --noinput

# Raccolta file statici Django (CSS admin)
echo "📁 Raccolta file statici Django..."
python manage.py collectstatic --noinput

# Creazione admin automatica
echo "👤 Creazione admin automatica..."
python manage.py create_admin

# Avvio server
echo "🌐 Avvio server Django..."
exec python manage.py runserver 0.0.0.0:$PORT 