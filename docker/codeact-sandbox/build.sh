#!/bin/bash
# Build CodeAct Sandbox Docker image

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building CodeAct Sandbox from $SCRIPT_DIR..."
docker build -t coderabbit-sandbox:latest "$SCRIPT_DIR"

echo "Testing sandbox..."
docker run --rm \
  --memory=512m \
  --cpus=1 \
  --network=none \
  coderabbit-sandbox:latest \
  python3 -c "import ast, re, json, pandas, numpy, networkx; print('All imports successful')"

echo "Sandbox ready!"
echo "Image: coderabbit-sandbox:latest"
