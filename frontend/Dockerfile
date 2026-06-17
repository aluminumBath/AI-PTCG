# Frontend image: build the Vite app, serve static files via nginx.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Inject the backend URL at container start (no rebuild needed). Set API_BASE
# to your backend's public URL in production; defaults to same-host :8000.
COPY docker-entrypoint.sh /docker-entrypoint.d/99-api-base.sh
RUN chmod +x /docker-entrypoint.d/99-api-base.sh

EXPOSE 80
