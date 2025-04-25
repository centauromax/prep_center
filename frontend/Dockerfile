# frontend/Dockerfile
# Usa un'immagine Nginx leggera
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Imposta la directory di lavoro
WORKDIR /usr/share/nginx/html

# Copia la configurazione Nginx personalizzata (la creeremo dopo)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia gli asset statici delle tue app
WORKDIR /usr/share/nginx/html # Imposto WORKDIR prima di COPY per percorsi relativi
COPY ./fbasaving/static/fbasaving/css ./fbasaving/static/css/
COPY ./fbasaving/static/fbasaving/js ./fbasaving/static/js/
COPY ./fbasaving/static/fbasaving/images ./fbasaving/static/images/ # Nuova riga per le immagini

# Aggiungi qui altre app quando necessario:
# COPY ./altraApp/static/specific_assets/css ./altraApp/static/css/

# Esponi la porta standard di Nginx
EXPOSE 8080

# Comando per avviare Nginx in foreground
CMD ["nginx", "-g", "daemon off;"] 