FROM python:3.14-slim AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM cgr.dev/chainguard/python:latest

WORKDIR /app

ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION}
ENV PYTHONPATH=/usr/local/lib/python3.14/site-packages

COPY --from=builder /install /usr/local
COPY . .

EXPOSE 5000

CMD ["/usr/local/bin/gunicorn", "-w", "2", "-k", "gthread", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
