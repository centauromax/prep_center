#!/bin/bash
set -e

echo "🚀 Avvio script di release..."

echo "📦 Esecuzione migrazioni database..."
python manage.py migrate --noinput

echo "📁 Raccolta file statici Django..."
python manage.py collectstatic --noinput --clear

echo "👤 Creazione admin automatica..."
python manage.py create_admin

echo "✅ Script di release completato con successo." 