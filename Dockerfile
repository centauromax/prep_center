FROM node:18-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# Crea il file di configurazione per serve
RUN echo '{\
  "rewrites": [\
    { "source": "/picture_check/**", "destination": "/index.html" },\
    { "source": "/en/picture_check/**", "destination": "/index.html" },\
    { "source": "/it/picture_check/**", "destination": "/index.html" }\
  ],\
  "redirects": [\
    { "source": "/fbasaving/**", "destination": "https://prepcenter-production.up.railway.app/fbasaving/:splat" },\
    { "source": "/en/fbasaving/**", "destination": "https://prepcenter-production.up.railway.app/en/fbasaving/:splat" },\
    { "source": "/it/fbasaving/**", "destination": "https://prepcenter-production.up.railway.app/it/fbasaving/:splat" }\
  ]\
}' > ./build/serve.json

RUN npm install -g serve
EXPOSE 8080
CMD ["serve", "-s", "build", "-l", "8080"] 