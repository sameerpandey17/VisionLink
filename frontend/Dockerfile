# syntax=docker/dockerfile:1.4
# BuildKit required: DOCKER_BUILDKIT=1

# DOCKER BUILD OPTIMIZATION
# --------------------------
# Uses `npm ci` instead of `npm install`:
#   - `npm ci` is 2-3x faster than `npm install` because it reads
#     package-lock.json exactly (no dependency resolution).
#   - `--prefer-offline` uses the BuildKit cache mount if packages
#     are already cached from a previous build.
#
# Layer ordering ensures cache efficiency:
#   1. Copy package*.json FIRST (only changes when deps change)
#   2. Run npm ci (cached unless package*.json changed)
#   3. Copy source code LAST (changes frequently, but doesn't bust npm cache)

FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
