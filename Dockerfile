# Dockerfile for node simulator
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy & install only the Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy in your node simulator script
COPY node.py ./

# Default entrypoint runs the node
ENTRYPOINT ["python", "node.py"] 