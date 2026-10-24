# Sanad `web` image: builds the SPA, then serves it with nginx (non-root, port 8080).
# Build context is the repo root (it needs deploy/nginx.conf); see Dockerfile.dockerignore.

ARG NODE_IMAGE=node:24.22.1-trixie-slim
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.30.6-alpine3.24

# The bundle is plain JS/CSS, so build on the native platform even when targeting another.
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
# Digits in the Arabic UI (latn|arab), baked into the bundle: Vite exposes VITE_* variables
# from the build environment. docker-compose.yml passes AR_NUMBERING from .env.
ARG VITE_AR_NUMBERING=latn
RUN npm run build

FROM ${NGINX_IMAGE} AS runtime
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 8080
