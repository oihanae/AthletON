# AthletON - Dockerfile (Render-ready)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiamos la app principal
COPY athleton_app.py ./

# ✅ Creamos la carpeta .streamlit y el config dentro durante el build
RUN mkdir -p /app/.streamlit && printf "[server]\nheadless = true\nenableCORS = false\n\n[browser]\ngatherUsageStats = false\n" > /app/.streamlit/config.toml

# Base de datos local (demo)
ENV ATHLETON_DB=/app/athleton.db

# Lanzar Streamlit en el puerto que Render asigna
CMD ["/bin/sh", "-c", "streamlit run athleton_app.py --server.port $PORT --server.address 0.0.0.0"]
