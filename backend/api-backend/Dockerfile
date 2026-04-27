FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y netcat-traditional && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD uvicorn main:app --host :: --port ${PORT:-8001}

