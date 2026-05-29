# Web — React SPA built with Vite, served by nginx.
# Build context: platform/ (so deploy/nginx.conf is accessible)
#
# Layer order: package.json → npm ci (cached) → source → build

FROM node:20-alpine AS build
WORKDIR /app

# ── Step 1: install deps (cached until package.json / package-lock.json change)
COPY web/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --silent

# ── Step 2: copy source and build (only rebuilds on source changes)
COPY web/ .
RUN npm run build

FROM nginx:1.27-alpine AS app
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
