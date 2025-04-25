# frontend/Dockerfile
# Usa l'immagine ufficiale Nginx Alpine
FROM nginx:alpine

# Imposta la directory di lavoro
WORKDIR /usr/share/nginx/html

# Copia la configurazione Nginx personalizzata
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Crea le directory necessarie
RUN mkdir -p /usr/share/nginx/html/fbasaving/static/css
RUN mkdir -p /usr/share/nginx/html/fbasaving/static/js
RUN mkdir -p /usr/share/nginx/html/fbasaving/static/images
RUN mkdir -p /usr/share/nginx/html/images

# Copia i file statici dell'app fbasaving in modo esplicito
COPY fbasaving/static/fbasaving/css /usr/share/nginx/html/fbasaving/static/css
COPY fbasaving/static/fbasaving/js /usr/share/nginx/html/fbasaving/static/js
COPY fbasaving/static/fbasaving/images /usr/share/nginx/html/fbasaving/static/images

# Copia il logo anche alla radice per compatibilità
COPY fbasaving/static/fbasaving/images/logo.jpg /usr/share/nginx/html/images/logo.jpg

# Copia il file 404.html
COPY 404.html /usr/share/nginx/html/404.html

# Aggiungi qui altre app quando necessario:
# COPY ./altraApp/static/specific_assets/css ./altraApp/static/css/

# Esponi la porta standard di Nginx
EXPOSE 8080

# Comando per avviare Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
