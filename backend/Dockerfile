FROM python:3.11-slim AS builder
WORKDIR /app

# only install build-time dependencies
RUN apt-get update && apt-get install -y --no-install-recommends build-essential

# install poetry and lock dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry \
 && poetry config virtualenvs.create false \
 && poetry install --only main --no-ansi --no-interaction --no-root


COPY . .

# runtime
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 file poppler-utils tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*


COPY --from=builder /usr/local /usr/local
COPY app app
COPY worker worker

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
