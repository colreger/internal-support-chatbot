FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip3 install --no-cache-dir -r requirements.txt

ENV HF_HUB_DISABLE_TELEMETRY=1 \
    SENTENCE_TRANSFORMERS_HOME=/opt/embedding-models

# Only public weights are downloaded at build time; app inference is offline.
RUN python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")'

COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "frontend.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0"]
