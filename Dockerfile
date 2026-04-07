FROM python:3.12-slim AS builder

WORKDIR /build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install --user --no-cache-dir --no-compile -r requirements.txt

FROM python:3.12-slim

WORKDIR /app
ENV PATH=/root/.local/bin:$PATH
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=builder /root/.local /root/.local
COPY app/ ./app/
RUN mkdir -p /app/logs \
    && find /root/.local -type d -name "__pycache__" -prune -exec rm -rf '{}' + \
    && find /root/.local -type f -name "*.pyc" -delete \
    && find /root/.local -type d \( -iname "tests" -o -iname "test" \) -prune -exec rm -rf '{}' +

EXPOSE 9999
CMD ["python", "-m", "uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "9999"]
