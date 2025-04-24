# frontend/Dockerfile
# Usa un'immagine Nginx leggera
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Imposta la directory di lavoro
WORKDIR /usr/share/nginx/html

# Copia la configurazione Nginx personalizzata (la creeremo dopo)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia gli asset statici delle tue app
# Manteniamo la struttura originale per semplicità nel conf
COPY ./fbasaving/static ./fbasaving/static
# Aggiungi qui altre app quando necessario:
# COPY ./altraApp/static ./altraApp/static

# Esponi la porta standard di Nginx
EXPOSE 8080

# Comando per avviare Nginx in foreground
CMD ["nginx", "-g", "daemon off;"] 