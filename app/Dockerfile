FROM node:22-alpine AS frontend
WORKDIR /src/app/frontend
COPY app/frontend/package*.json ./
RUN npm ci
COPY app/frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime
ARG PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home /app app
COPY pyproject.toml ./
COPY app/ ./app/
COPY --from=frontend /src/app/static ./app/static/
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" .
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT}"]