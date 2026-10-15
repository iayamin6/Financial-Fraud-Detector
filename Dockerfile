FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false FRAUD_SECURITY_MODE=authenticated
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --uid 10001 --create-home fraud && mkdir -p /app/runtime && chown -R fraud:fraud /app/runtime
USER fraud
EXPOSE 8765
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
