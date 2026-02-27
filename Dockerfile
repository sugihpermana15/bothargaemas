# syntax=docker/dockerfile:1
# Base image includes Playwright + browsers + OS deps (safe JS-render fallback)
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY emasbot/requirements.txt /app/emasbot/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/emasbot/requirements.txt

# Copy app
COPY emasbot/ /app/emasbot/

WORKDIR /app/emasbot

# No ports exposed: this is a background worker
CMD ["python", "main.py"]
