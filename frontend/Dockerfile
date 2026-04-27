
FROM node:20-alpine AS build
WORKDIR /app
# Mismo origen vía Nginx (/api) — válido en localhost:8080 y detrás de ngrok
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /app
RUN npm i -g serve
COPY --from=build /app/dist ./dist
# Opción 1: solo Railway
CMD ["sh", "-c", "serve -s dist -l $PORT"]

