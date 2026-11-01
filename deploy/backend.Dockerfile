# Archway's backend (FastAPI + LangGraph), for the server.
# Built from the repository root: docker build -f deploy/backend.Dockerfile .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Only the code the server needs: no tests, no local data, no .env (secrets arrive as environment variables).
COPY backend/app ./app
COPY backend/fixtures ./fixtures
COPY backend/scripts ./scripts

# A user without root rights runs the server.
RUN useradd --create-home --uid 10001 archway && mkdir -p /data && chown archway /data
USER archway

EXPOSE 8000
# One worker: background research tasks and the sign-in limits live in this one process.
# --proxy-headers: the visitor's real address comes from Caddy (the only thing that can reach this port).
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "2"]
