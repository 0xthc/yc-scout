FROM python:3.12-slim

WORKDIR /app

# Install deps first (layer-cached separately from code)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code (includes enrichment package)
COPY backend/ backend/

EXPOSE 8000

# Use 2 workers for Render free tier (1 vCPU)
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
