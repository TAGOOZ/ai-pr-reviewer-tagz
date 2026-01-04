# Setting Up CodeRabbit AI for Public Testing

## Problem

GitHub webhooks require a **public URL** - they cannot reach `localhost`.

## Solutions

### Option 1: Use ngrok (Recommended)

**Install ngrok:**
```bash
# Linux (Debian/Ubuntu)
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list && \
sudo apt update && sudo apt install ngrok

# Or download directly
wget https://bin.equinox.io/c/4VmDzA7iaKbL3fwWzMzaKxXz8Kc/ngrok-v3-stable-linux-amd64.zip
unzip ngrok-v3-stable-linux-amd64.zip
sudo mv ngrok /usr/local/bin
```

**Get free ngrok account:**
1. Go to: https://dashboard.ngrok.com/signup
2. Sign up for free account
3. Get authtoken from dashboard

**Authenticate ngrok:**
```bash
ngrok config add-authtoken YOUR_NGROK_AUTH_TOKEN
```

**Expose API Gateway:**
```bash
# Terminal 1: Start ngrok tunnel for API Gateway
ngrok http 8080
```

This will give you a public URL like: `https://abc123.ngrok-free.app`

**Update GitHub Webhook:**
1. Go to: https://github.com/TAGOOZ/ai-pr-reviewer-tagz/settings/hooks
2. Click "Add webhook"
3. Payload URL: `https://abc123.ngrok-free.app/webhooks/github`
4. Content type: `application/json`
5. Secret: (leave empty for dev, or set a secret)
6. Events: Pull requests
7. Click "Add webhook"

**Start CodeRabbit Services:**
```bash
# Terminal 2: Start Python AI Pipeline
cd /teamspace/studios/this_studio/ai-pr-reviewer-tagz
OPENAI_API_KEY=sk-dummy PORT=8000 \
  poetry run uvicorn coderabbit_ai.server:app --host 127.0.0.1 --port 8000

# Terminal 3: Start Mock API Gateway
cd /teamspace/studios/this_studio/ai-pr-reviewer-tagz
API_GATEWAY_PORT=8080 \
  poetry run uvicorn scripts.mock_api_gateway:app --host 127.0.0.1 --port 8080
```

**Create New PR to Test:**
1. Make a small change to any file
2. Create PR
3. CodeRabbit will receive webhook via ngrok and review it!

---

### Option 2: Cloudflare Tunnel (Alternative)

```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64

# Start tunnel
./cloudflared-linux-amd64 tunnel --url http://localhost:8080
```

---

### Option 3: Using GitHub CLI (No tunneling needed)

```bash
# Install GitHub CLI (if not installed)
# https://cli.github.com/

# Test CodeRabbit AI locally with gh CLI
gh pr view 4 --repo TAGOOZ/ai-pr-reviewer-tagz --json files | \
  jq '.files[].path' | \
  xargs -I {} sh -c 'cat {}' | \
  curl -X POST http://localhost:8000/review \
    -H "Content-Type: application/json" \
    -d @/dev/stdin
```

---

### Option 4: Deploy to Cloud (Production approach)

**Deploy to Render/Vercel/Railway:**

1. Push to repository with deployment config
2. Get public URL
3. Update GitHub webhook to point to public URL

**Example using Render:**
- Create `render.yaml`
- Push to GitHub
- Render auto-deploys
- Get public URL: `https://your-app.onrender.com`
- Configure GitHub webhook to: `https://your-app.onrender.com/webhooks/github`

---

## Quick Start with ngrok

**Step 1: Install ngrok**
```bash
# Download
wget https://bin.equinox.io/c/4VmDzA7iaKbL3fwWzMzaKxXz8Kc/ngrok-v3-stable-linux-amd64.zip
unzip ngrok-v3-stable-linux-amd64.zip
sudo mv ngrok /usr/local/bin
```

**Step 2: Sign up and get token**
Go to: https://dashboard.ngrok.com/signup

**Step 3: Configure ngrok**
```bash
ngrok config add-authtoken YOUR_TOKEN_HERE
```

**Step 4: Start tunnel**
```bash
# Keep this running
ngrok http 8080 --log=stdout
```

You'll see:
```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:8080
```

**Step 5: Start services** (in other terminals)
```bash
# Terminal 2 - Python AI Pipeline
OPENAI_API_KEY=sk-dummy PORT=8000 poetry run uvicorn coderabbit_ai.server:app --host 127.0.0.1 --port 8000

# Terminal 3 - API Gateway (use port 8081 instead to avoid conflict)
API_GATEWAY_PORT=8081 poetry run uvicorn scripts.mock_api_gateway:app --host 127.0.0.1 --port 8081
```

**Step 6: Update webhook**
1. GitHub Repo Settings → Webhooks → Add webhook
2. URL: `https://abc123.ngrok-free.app/webhooks/github`
3. Events: Pull requests
4. Add webhook

**Step 7: Create test PR**
Make any change and create PR → CodeRabbit will review it!

---

## Testing Without Webhook (Manual)

If you don't want to set up ngrok, test manually:

```bash
# Get PR #4 files
gh pr view 4 --repo TAGOOZ/ai-pr-reviewer-tagz --json > pr.json

# Manually trigger review (with proper format)
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d @pr.json
```

---

## Summary

| Solution | Complexity | Cost | Public URL |
|----------|-------------|-------|-------------|
| ngrok | Easy | Free | ✓ Yes |
| Cloudflare Tunnel | Easy | Free | ✓ Yes |
| Cloud Deployment | Medium | Pay-as-you-go | ✓ Yes |
| Local Manual | Easy | Free | ✗ No |

**Recommended**: Use ngrok for quick public URL to test webhooks!
