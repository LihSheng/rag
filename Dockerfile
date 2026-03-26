FROM node:20-slim AS frontend-builder

WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace/src \
    FRONTEND_DIST_DIR=/opt/ragstack-ui

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

COPY --from=frontend-builder /workspace/frontend/dist /opt/ragstack-ui

COPY docker/entrypoint.sh /usr/local/bin/rag-entrypoint
RUN chmod +x /usr/local/bin/rag-entrypoint

ENTRYPOINT ["rag-entrypoint"]
CMD []
