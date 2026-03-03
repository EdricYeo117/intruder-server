FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libstdc++6 \
    libgcc-s1 \
    libgomp1 \
    libgl1 \
    libxcb1 \
    libx11-6 \
    libxext6 \
    libxrender1 \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# syntax=docker/dockerfile:1.6
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt \
 && pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY . .
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]