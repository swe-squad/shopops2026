FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --system --uid 1001 app && mkdir -p /data && chown app:app /data
COPY --chown=app:app app ./app
COPY --chown=app:app config ./config
COPY --chown=app:app knowledge ./knowledge
COPY --chown=app:app fixtures ./fixtures
COPY --chown=app:app contracts ./contracts
COPY --chown=app:app scripts ./scripts
USER app

EXPOSE 8000
VOLUME ["/data"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --no-access-log"]
