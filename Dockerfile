FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY src/ src/

# Expose gateway port
EXPOSE 8080

# Run gateway
CMD ["python", "-m", "gateway.main"]
