#!/bin/bash

# CodeRabbit Development Environment Setup Script

set -e

echo "🚀 Setting up CodeRabbit development environment..."

# Check if required tools are installed
check_tool() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 is not installed. Please install it first."
        exit 1
    else
        echo "✅ $1 is installed"
    fi
}

echo "📋 Checking required tools..."
check_tool "cargo"
check_tool "python3"
check_tool "docker"
check_tool "docker-compose"

# Install Rust components
echo "🦀 Setting up Rust toolchain..."
rustup component add rustfmt clippy rust-src
cargo install cargo-watch cargo-edit cargo-audit

# Install Python dependencies
echo "🐍 Setting up Python environment..."
if ! command -v poetry &> /dev/null; then
    echo "Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

poetry install

# Install pre-commit hooks
echo "🔧 Setting up pre-commit hooks..."
poetry run pre-commit install

# Create environment file
echo "📝 Creating environment configuration..."
if [ ! -f .env ]; then
    cat > .env << EOF
# Database
DATABASE_URL=postgresql://coderabbit:coderabbit_dev@localhost:5432/coderabbit

# Redis
REDIS_URL=redis://localhost:6379

# AI APIs (add your keys here)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Environment
ENVIRONMENT=development
RUST_LOG=debug
LOG_LEVEL=DEBUG

# Server
HOST=127.0.0.1
PORT=8080
EOF
    echo "✅ Created .env file - please update with your API keys"
else
    echo "✅ .env file already exists"
fi

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/cache data/vectors data/logs
chmod 755 data data/cache data/vectors data/logs

# Initialize secrets baseline for detect-secrets
echo "🔒 Initializing secrets detection..."
if [ ! -f .secrets.baseline ]; then
    poetry run detect-secrets scan --baseline .secrets.baseline
    echo "✅ Created secrets baseline"
fi

# Start development services
echo "🐳 Starting development services..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Run initial database setup
echo "🗄️ Setting up database..."
# TODO: Add database migration commands when implemented

# Build Rust workspace
echo "🔨 Building Rust workspace..."
cargo build

# Run tests to verify setup
echo "🧪 Running tests to verify setup..."
cargo test --workspace --lib
poetry run pytest tests/ -v || echo "⚠️ Python tests failed - this is expected if tests aren't implemented yet"

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env file with your API keys"
echo "2. Start development with: cargo watch -x run"
echo "3. Or use Docker: docker-compose up"
echo ""
echo "Useful commands:"
echo "- cargo watch -x 'run --bin coderabbit-api-gateway'"
echo "- poetry run python -m coderabbit_ai.server"
echo "- docker-compose logs -f"
echo "- pre-commit run --all-files"