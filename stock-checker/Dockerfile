FROM python:3.13-slim AS base

WORKDIR /app

COPY pyproject.toml .
COPY stock_checker/ stock_checker/

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "stock_checker"]
