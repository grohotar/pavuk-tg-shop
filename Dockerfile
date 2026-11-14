FROM python:3.11-slim AS builder

WORKDIR /app

# Exact versions running in prod (pip freeze); requirements.txt leaves some unpinned.
COPY requirements.lock .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.lock

FROM python:3.11-slim

WORKDIR /app
 
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

COPY . .

RUN rm -rf /root/.cache

CMD ["python", "main.py"]
