FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace/src

WORKDIR /workspace

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

COPY docker/entrypoint.sh /usr/local/bin/rag-entrypoint
RUN chmod +x /usr/local/bin/rag-entrypoint

ENTRYPOINT ["rag-entrypoint"]
CMD []

