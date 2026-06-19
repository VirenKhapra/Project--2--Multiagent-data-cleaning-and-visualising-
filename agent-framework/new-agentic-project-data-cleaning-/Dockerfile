FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app/src

# We want to run both the API server (uvicorn) and the ARQ worker.
# An easy way is to use a simple bash script.
COPY run.sh .
RUN chmod +x run.sh

CMD ["./run.sh"]
