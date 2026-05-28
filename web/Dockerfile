# Multi-stage build: Node builds the React SPA, nginx serves it.
# Nginx also reverse-proxies API paths to the gateway service.
# Build context: platform/ (so deploy/nginx.conf is accessible)

FROM node:20-alpine AS build
WORKDIR /app
COPY web/package*.json ./
RUN npm ci --silent
COPY web/ .
RUN npm run build

FROM nginx:1.27-alpine AS app
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
