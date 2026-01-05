#!/bin/bash
# =============================================================================
# Webhook Testing Script for AI PR Reviewer
# =============================================================================
# This script automates the setup and testing of the webhook-based PR review
# system using ngrok for tunneling.
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NGROK_LOG="$PROJECT_ROOT/logs/ngrok.log"
API_LOG="$PROJECT_ROOT/logs/api-gateway.log"
AI_LOG="$PROJECT_ROOT/logs/ai-pipeline.log"

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed!"
        return 1
    fi
    return 0
}

wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=${3:-30}
    local attempt=0
    
    log_info "Waiting for $name to be ready..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            log_success "$name is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    log_error "$name failed to start after $max_attempts seconds"
    return 1
}

# -----------------------------------------------------------------------------
# Check Prerequisites
# -----------------------------------------------------------------------------
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=0
    
    check_command "ngrok" || missing=$((missing + 1))
    check_command "cargo" || missing=$((missing + 1))
    check_command "poetry" || missing=$((missing + 1))
    check_command "docker" || missing=$((missing + 1))
    check_command "curl" || missing=$((missing + 1))
    
    # Check .env file
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_error ".env file not found! Copy .env.example to .env and configure it."
        missing=$((missing + 1))
    fi
    
    if [ $missing -gt 0 ]; then
        log_error "$missing prerequisites missing!"
        exit 1
    fi
    
    log_success "All prerequisites satisfied!"
}

# -----------------------------------------------------------------------------
# Start Database Services
# -----------------------------------------------------------------------------
start_databases() {
    log_info "Starting PostgreSQL and Redis..."
    cd "$PROJECT_ROOT"
    docker-compose up -d postgres redis
    
    # Wait for databases to be ready
    sleep 5
    log_success "Database services started!"
}

# -----------------------------------------------------------------------------
# Start API Gateway
# -----------------------------------------------------------------------------
start_api_gateway() {
    log_info "Starting API Gateway on port 8080..."
    cd "$PROJECT_ROOT"
    
    # Kill any existing process on port 8080
    lsof -ti:8080 | xargs kill -9 2>/dev/null || true
    
    CODERABBIT_ENV=development RUST_LOG=info,coderabbit=debug \
        cargo run --bin api-gateway > "$API_LOG" 2>&1 &
    
    API_PID=$!
    echo $API_PID > "$PROJECT_ROOT/logs/api-gateway.pid"
    
    wait_for_service "http://localhost:8080/health" "API Gateway"
}

# -----------------------------------------------------------------------------
# Start AI Pipeline
# -----------------------------------------------------------------------------
start_ai_pipeline() {
    log_info "Starting AI Pipeline on port 8081..."
    cd "$PROJECT_ROOT/python"
    
    # Kill any existing process on port 8081
    lsof -ti:8081 | xargs kill -9 2>/dev/null || true
    
    CODERABBIT_ENV=development LOG_LEVEL=INFO \
        poetry run python -m coderabbit_ai.server > "$AI_LOG" 2>&1 &
    
    AI_PID=$!
    echo $AI_PID > "$PROJECT_ROOT/logs/ai-pipeline.pid"
    
    wait_for_service "http://localhost:8081/health" "AI Pipeline"
}

# -----------------------------------------------------------------------------
# Start Ngrok Tunnel
# -----------------------------------------------------------------------------
start_ngrok() {
    log_info "Starting ngrok tunnel..."
    
    # Kill any existing ngrok process
    pkill -f "ngrok http" 2>/dev/null || true
    sleep 1
    
    ngrok http 8080 --log=stdout > "$NGROK_LOG" 2>&1 &
    NGROK_PID=$!
    echo $NGROK_PID > "$PROJECT_ROOT/logs/ngrok.pid"
    
    # Wait for ngrok to start and get the URL
    sleep 3
    
    # Get the public URL from ngrok API
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -oE '"public_url":"https://[^"]+' | head -1 | cut -d'"' -f4)
    
    if [ -z "$NGROK_URL" ]; then
        log_error "Failed to get ngrok URL. Check $NGROK_LOG for details."
        log_warning "You may need to authenticate ngrok: ngrok config add-authtoken YOUR_TOKEN"
        return 1
    fi
    
    log_success "Ngrok tunnel established!"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════════════"
    echo -e "${GREEN}WEBHOOK URL:${NC} ${NGROK_URL}/api/webhooks/github"
    echo "═══════════════════════════════════════════════════════════════════════════"
    echo ""
    
    # Save URL to file for reference
    echo "$NGROK_URL" > "$PROJECT_ROOT/logs/ngrok-url.txt"
}

# -----------------------------------------------------------------------------
# Display GitHub Webhook Setup Instructions
# -----------------------------------------------------------------------------
show_webhook_instructions() {
    NGROK_URL=$(cat "$PROJECT_ROOT/logs/ngrok-url.txt" 2>/dev/null || echo "https://YOUR_NGROK_URL")
    WEBHOOK_SECRET=$(grep GITHUB_WEBHOOK_SECRET "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2 || echo "YOUR_WEBHOOK_SECRET")
    
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    GITHUB WEBHOOK CONFIGURATION                           ║"
    echo "╠═══════════════════════════════════════════════════════════════════════════╣"
    echo "║                                                                           ║"
    echo "║  1. Go to your GitHub repository                                          ║"
    echo "║  2. Navigate to: Settings → Webhooks → Add webhook                        ║"
    echo "║  3. Configure:                                                            ║"
    echo "║                                                                           ║"
    echo "║     Payload URL: ${NGROK_URL}/api/webhooks/github"
    echo "║     Content type: application/json                                        ║"
    echo "║     Secret: $WEBHOOK_SECRET"
    echo "║                                                                           ║"
    echo "║  4. Select events:                                                        ║"
    echo "║     ☑ Pull requests                                                       ║"
    echo "║     ☑ Pull request reviews                                                ║"
    echo "║     ☑ Pull request review comments                                        ║"
    echo "║     ☑ Issue comments                                                      ║"
    echo "║                                                                           ║"
    echo "║  5. Click 'Add webhook'                                                   ║"
    echo "║                                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo ""
}

# -----------------------------------------------------------------------------
# Monitor Logs
# -----------------------------------------------------------------------------
monitor_logs() {
    log_info "Monitoring logs (Ctrl+C to stop)..."
    echo ""
    echo "═══════════════════════════════════════════════════════════════════════════"
    echo "Watching for webhook events..."
    echo "═══════════════════════════════════════════════════════════════════════════"
    
    tail -f "$API_LOG" "$AI_LOG" 2>/dev/null
}

# -----------------------------------------------------------------------------
# Stop All Services
# -----------------------------------------------------------------------------
stop_all() {
    log_info "Stopping all services..."
    
    # Stop ngrok
    if [ -f "$PROJECT_ROOT/logs/ngrok.pid" ]; then
        kill $(cat "$PROJECT_ROOT/logs/ngrok.pid") 2>/dev/null || true
        rm "$PROJECT_ROOT/logs/ngrok.pid"
    fi
    pkill -f "ngrok http" 2>/dev/null || true
    
    # Stop API Gateway
    if [ -f "$PROJECT_ROOT/logs/api-gateway.pid" ]; then
        kill $(cat "$PROJECT_ROOT/logs/api-gateway.pid") 2>/dev/null || true
        rm "$PROJECT_ROOT/logs/api-gateway.pid"
    fi
    lsof -ti:8080 | xargs kill -9 2>/dev/null || true
    
    # Stop AI Pipeline
    if [ -f "$PROJECT_ROOT/logs/ai-pipeline.pid" ]; then
        kill $(cat "$PROJECT_ROOT/logs/ai-pipeline.pid") 2>/dev/null || true
        rm "$PROJECT_ROOT/logs/ai-pipeline.pid"
    fi
    lsof -ti:8081 | xargs kill -9 2>/dev/null || true
    
    log_success "All services stopped!"
}

# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
health_check() {
    log_info "Running health checks..."
    
    echo ""
    echo "Service Status:"
    echo "───────────────────────────────────────"
    
    # API Gateway
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "  API Gateway (8080):  ${GREEN}✓ Running${NC}"
    else
        echo -e "  API Gateway (8080):  ${RED}✗ Not running${NC}"
    fi
    
    # AI Pipeline
    if curl -s http://localhost:8081/health > /dev/null 2>&1; then
        echo -e "  AI Pipeline (8081):  ${GREEN}✓ Running${NC}"
    else
        echo -e "  AI Pipeline (8081):  ${RED}✗ Not running${NC}"
    fi
    
    # Ngrok
    if curl -s http://localhost:4040/api/tunnels > /dev/null 2>&1; then
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -oP '"public_url":"https://[^"]+' | head -1 | cut -d'"' -f4)
        echo -e "  Ngrok Tunnel:        ${GREEN}✓ Active${NC}"
        echo -e "                       URL: $NGROK_URL"
    else
        echo -e "  Ngrok Tunnel:        ${RED}✗ Not running${NC}"
    fi
    
    # PostgreSQL
    if docker ps | grep -q postgres; then
        echo -e "  PostgreSQL:          ${GREEN}✓ Running${NC}"
    else
        echo -e "  PostgreSQL:          ${RED}✗ Not running${NC}"
    fi
    
    # Redis
    if docker ps | grep -q redis; then
        echo -e "  Redis:               ${GREEN}✓ Running${NC}"
    else
        echo -e "  Redis:               ${RED}✗ Not running${NC}"
    fi
    
    echo "───────────────────────────────────────"
    echo ""
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
case "${1:-}" in
    start)
        check_prerequisites
        start_databases
        start_api_gateway
        start_ai_pipeline
        start_ngrok
        show_webhook_instructions
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        check_prerequisites
        start_databases
        start_api_gateway
        start_ai_pipeline
        start_ngrok
        show_webhook_instructions
        ;;
    status|health)
        health_check
        ;;
    logs)
        monitor_logs
        ;;
    ngrok)
        start_ngrok
        show_webhook_instructions
        ;;
    instructions)
        show_webhook_instructions
        ;;
    *)
        echo ""
        echo "╔═══════════════════════════════════════════════════════════════════════════╗"
        echo "║             AI PR REVIEWER - WEBHOOK TESTING SCRIPT                       ║"
        echo "╚═══════════════════════════════════════════════════════════════════════════╝"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|ngrok|instructions}"
        echo ""
        echo "Commands:"
        echo "  start        - Start all services and ngrok tunnel"
        echo "  stop         - Stop all services"
        echo "  restart      - Restart all services"
        echo "  status       - Check status of all services"
        echo "  logs         - Monitor logs from all services"
        echo "  ngrok        - Start only ngrok tunnel (services must be running)"
        echo "  instructions - Show GitHub webhook setup instructions"
        echo ""
        exit 1
        ;;
esac
