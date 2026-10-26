# Sentinel V4 demo: web console + API in one container. No keys or passwords are baked in;
# set SENTINEL_DEMO_PASSWORD at run time (docs/HOSTING.md).
FROM node:20-bookworm-slim AS web
WORKDIR /build
COPY web/package.json web/package-lock.json web/
RUN cd web && npm ci
COPY web/ web/
COPY specs/contracts/ specs/contracts/
RUN cd web && npm run build

FROM python:3.12-slim
ARG SENTINEL_SOURCE_COMMIT=UNAVAILABLE
ENV SENTINEL_SOURCE_COMMIT=${SENTINEL_SOURCE_COMMIT}
LABEL org.opencontainers.image.revision=${SENTINEL_SOURCE_COMMIT}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
WORKDIR /app
COPY requirements-runtime.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt -r requirements-api.txt
COPY src/ src/
COPY specs/contracts/ specs/contracts/
COPY specs/approvals/ specs/approvals/
COPY data/geospatial_v3/ data/geospatial_v3/
COPY data/raw_docs/ data/raw_docs/
COPY data/eval_results/ data/eval_results/
COPY data/eval_v3/phase10/ data/eval_v3/phase10/
COPY data/eval_v3/phase13/ data/eval_v3/phase13/
COPY data/constraints_v4/ data/constraints_v4/
COPY data/demo_v4/ data/demo_v4/
COPY --from=web /build/web/dist web/dist
ENV SENTINEL_WEB_DIST=/app/web/dist SENTINEL_DEMO_SOURCE=RECORDED PORT=8000
RUN useradd --create-home --uid 10001 sentinel
USER sentinel
EXPOSE 8000
CMD ["sh", "-c", "exec python -m uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
