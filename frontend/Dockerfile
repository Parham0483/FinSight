FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (layer cache)
COPY package.json package-lock.json* ./
RUN npm ci

# Build
COPY . .
RUN npm run build

# The built dist/ is used as a named volume by nginx
FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/dist ./static
CMD ["sh", "-c", "cp -a /app/static/. /dist/"]
