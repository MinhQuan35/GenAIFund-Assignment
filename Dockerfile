FROM node:22-alpine AS web-build

WORKDIR /workspace/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY apps/api/requirements.txt /workspace/apps/api/requirements.txt
RUN pip install --no-cache-dir -r /workspace/apps/api/requirements.txt

COPY apps/api/src/ /workspace/apps/api/src/
COPY --from=web-build /workspace/apps/web/dist/ /workspace/apps/web/dist/

WORKDIR /workspace/apps/api
EXPOSE 8004
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004"]
