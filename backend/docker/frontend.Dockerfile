# ---------- Stage 1: build the Vite app ----------
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Runs vite directly; the type-check (tsc -b) is left to `npm run build` locally
RUN npx vite build

# ---------- Stage 2: serve static files with nginx ----------
FROM nginx:1.27-alpine AS production
COPY --from=dockerfiles nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]

# ---------- Optional: dev server with hot reload ----------
FROM node:22-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 4000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "4000"]
