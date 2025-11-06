#!/bin/bash
# Build CodeAct Sandbox Docker image

set -e

echo "Building CodeAct Sandbox..."
docker build -t coderabbit-sandbox:latest .

echo "Testing sandbox..."
docker run --rm \
  --memory=512m \
  --cpus=1 \
  --network=none \
  coderabbit-sandbox:latest \
  python3 -c "import ast, re, json, pandas, numpy, networkx; print('All imports successful')"

echo "Sandbox ready!"
echo "Image: coderabbit-sandbox:latest"
