# Frontend stage runs only when Person A's Vite app is in the build context.
# This branch may omit frontend/; the API still boots and serves /api.

FROM node:22-bookworm-slim AS frontend
WORKDIR /src
COPY . /src
RUN mkdir -p /frontend-dist \
    && if [ -f frontend/package.json ]; then \
         cd frontend \
         && if [ -f pnpm-lock.yaml ]; then \
              corepack enable && pnpm install --frozen-lockfile && pnpm run build; \
            elif [ -f yarn.lock ]; then \
              corepack enable && yarn install --frozen-lockfile && yarn build; \
            elif [ -f package-lock.json ]; then \
              npm ci && npm run build; \
            else \
              npm install && npm run build; \
            fi \
         && cp -a dist/. /frontend-dist/; \
       fi

FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY --from=frontend /frontend-dist /tmp/frontend-dist
RUN if [ -f /tmp/frontend-dist/index.html ]; then \
      mkdir -p /app/frontend/dist && cp -a /tmp/frontend-dist/. /app/frontend/dist/; \
    fi \
    && rm -rf /tmp/frontend-dist

# Free tier has no disk. /tmp is writable and empty on each boot; init_db reseeds.
ENV PYTHONPATH=/app \
    DATABASE_PATH=/tmp/fairlot.db \
    PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
