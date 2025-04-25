# Fase di build
FROM node:18-alpine as build

WORKDIR /app

# Copiamo i file necessari
COPY picture_check/package.json picture_check/package-lock.json* ./picture_check/
RUN cd picture_check && npm install

# Copiamo il resto del codice
COPY picture_check/ ./picture_check/

# Build dell'app
RUN cd picture_check && npm run build

# Crea la directory dist
RUN mkdir -p dist
RUN cp -r picture_check/build/* dist/picture_check/

# Fase di produzione
FROM node:18-alpine

WORKDIR /app

# Installiamo http-server
RUN npm install -g http-server

# Copiamo solo i file di build
COPY --from=build /app/dist /app/dist

# Esponiamo la porta
EXPOSE 8080

# Comando di avvio
CMD ["http-server", "dist", "-p", "8080", "--cors"] 