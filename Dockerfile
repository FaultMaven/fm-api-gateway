# FaultMaven API Gateway - PUBLIC Open Source Version
# Apache 2.0 License

FROM python:3.11-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir poetry==1.7.0
COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without dev

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src:$PYTHONPATH
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import httpx; httpx.get('http://localhost:8090/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8090"]
