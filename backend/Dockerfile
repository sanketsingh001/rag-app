FROM python:3.11-slim AS builder
WORKDIR /app

# install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libmagic1 poppler-utils tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

# install poetry and only lock dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry \
 && poetry config virtualenvs.create false \
 && poetry install --only main --no-ansi --no-interaction --no-root

# copy source code after installing dependencies
COPY . .

# runtime
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app app
COPY worker worker

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
