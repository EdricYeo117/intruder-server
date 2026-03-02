FROM python:3.11-slim

WORKDIR /app

# System deps commonly needed by mediapipe/opencv on slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libstdc++6 \
    libgcc-s1 \
    libgomp1 \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip tooling first (avoids many wheel install issues)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]