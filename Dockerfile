# Container image for the Lumen catalog UI on Cloud Run.
#
# The app reads catalog_metadata.json and embeddings.json, both of which are
# in the repository, so the image is self contained. lumen.db is not needed
# at runtime and is excluded by .dockerignore.

FROM python:3.12-slim

# Cloud Run injects PORT and expects the server to listen on it. The default
# here is only for running the image locally.
ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so editing the app does not rebuild this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Shell form on purpose, so $PORT is expanded at start up.
# 0.0.0.0 is required: Cloud Run cannot reach a server bound to localhost.
CMD streamlit run app.py \
      --server.port=$PORT \
      --server.address=0.0.0.0 \
      --server.headless=true \
      --browser.gatherUsageStats=false
