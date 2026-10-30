FROM python:3.14-slim AS python-base

FROM python-base AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python-base AS runtime

WORKDIR /app

ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION}
ENV PYTHONPATH=/usr/local/lib/python3.14/site-packages
ENV TZ=UTC
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=builder /install /usr/local
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY . .

USER 65532:65532

EXPOSE 5000

CMD ["/usr/local/bin/gunicorn", "-w", "2", "-k", "gthread", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
