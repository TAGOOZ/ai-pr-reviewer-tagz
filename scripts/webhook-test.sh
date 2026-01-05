#!/bin/bash

WEBHOOK_URL="https://earnings-statistics-minimum-county.trycloudflare.com/api/v1/webhook/github"
WEBHOOK_SECRET="a8211455fd96f134e736746f7ef10075b2b81d9f0758ac16ffe9ebec78f32aec"

echo "Testing webhook: $WEBHOOK_URL"

# Simple ping test
PAYLOAD='{"zen":"test"}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -binary | xxd -p -c 256)

curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Hub256-Signature-256: sha256=$SIGNATURE" \
  -d "$PAYLOAD"

echo "Test complete. Check server logs: ssh server 'cd content/ai-pr-reviewer-tagz && tail -50 logs/api-gateway.log'"
