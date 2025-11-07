"""Centralized configuration for CodeRabbit AI Pipeline.

This module provides configurable constants to avoid hardcoded values throughout the codebase.
All values can be overridden via environment variables.
"""

import os
from typing import Optional


def get_env_int(key: str, default: int) -> int:
    """Get integer value from environment or use default."""
    return int(os.getenv(key, str(default)))


def get_env_float(key: str, default: float) -> float:
    """Get float value from environment or use default."""
    return float(os.getenv(key, str(default)))


def get_env_str(key: str, default: str) -> str:
    """Get string value from environment or use default."""
    return os.getenv(key, default)


# ============================================================================
# Service URLs and Network Configuration
# ============================================================================

EMBEDDING_SERVICE_URL = get_env_str(
    "EMBEDDING_SERVICE_URL",
    "http://localhost:8081/embed"
)

VECTOR_SEARCH_SERVICE_URL = get_env_str(
    "VECTOR_SEARCH_SERVICE_URL",
    "http://localhost:8082/search"
)

SERVER_HOST = get_env_str("HOST", "127.0.0.1")
SERVER_PORT = get_env_int("PORT", 8081)
SERVER_WORKERS = get_env_int("WORKERS", 1)


# ============================================================================
# Timeout Configuration
# ============================================================================

# Network request timeouts (seconds)
HTTP_REQUEST_TIMEOUT = get_env_int("HTTP_REQUEST_TIMEOUT", 10)
STATIC_ANALYZER_TIMEOUT = get_env_int("STATIC_ANALYZER_TIMEOUT", 30)

# Agent execution timeouts (seconds)
AGENT_EXECUTION_TIMEOUT = get_env_int("AGENT_EXECUTION_TIMEOUT", 300)
SANDBOX_EXECUTION_TIMEOUT = get_env_int("SANDBOX_EXECUTION_TIMEOUT", 30)


# ============================================================================
# Sandbox Configuration
# ============================================================================

SANDBOX_MAX_MEMORY_MB = get_env_int("SANDBOX_MAX_MEMORY_MB", 512)
SANDBOX_MAX_CPUS = get_env_float("SANDBOX_MAX_CPUS", 1.0)
SANDBOX_MAX_OUTPUT_SIZE_BYTES = get_env_int(
    "SANDBOX_MAX_OUTPUT_SIZE_BYTES",
    1024 * 1024  # 1MB
)
SANDBOX_MAX_PROCESSES = get_env_int("SANDBOX_MAX_PROCESSES", 50)
SANDBOX_DOCKER_IMAGE = get_env_str(
    "SANDBOX_DOCKER_IMAGE",
    "coderabbit-sandbox:latest"
)


# ============================================================================
# Text Processing and Truncation Limits
# ============================================================================

# Character limits for truncation
TRUNCATE_ERROR_OUTPUT = get_env_int("TRUNCATE_ERROR_OUTPUT", 1000)
TRUNCATE_SANDBOX_OUTPUT = get_env_int("TRUNCATE_SANDBOX_OUTPUT", 1000)
TRUNCATE_STATIC_CONTEXT = get_env_int("TRUNCATE_STATIC_CONTEXT", 1000)
TRUNCATE_CODE_CHANGES = get_env_int("TRUNCATE_CODE_CHANGES", 5000)
TRUNCATE_VERIFICATION_TEXT = get_env_int("TRUNCATE_VERIFICATION_TEXT", 6000)


# ============================================================================
# Batch Processing Configuration
# ============================================================================

EMBEDDING_BATCH_SIZE = get_env_int("EMBEDDING_BATCH_SIZE", 32)
DEFAULT_TOP_K_RESULTS = get_env_int("DEFAULT_TOP_K_RESULTS", 5)


# ============================================================================
# Cache Configuration
# ============================================================================

CACHE_TTL_SECONDS = get_env_int("CACHE_TTL_SECONDS", 3600)
MAX_CACHE_SIZE_MB = get_env_int("MAX_CACHE_SIZE_MB", 1024)


# ============================================================================
# Optimization Configuration
# ============================================================================

MAX_OPTIMIZATION_CANDIDATES = get_env_int("MAX_OPTIMIZATION_CANDIDATES", 50)
MAX_OPTIMIZATION_ITERATIONS = get_env_int("MAX_OPTIMIZATION_ITERATIONS", 100)
OPTIMIZATION_EVAL_DATASET_SIZE = get_env_int(
    "OPTIMIZATION_EVAL_DATASET_SIZE",
    200
)
OPTIMIZATION_IMPROVEMENT_WINDOW = get_env_int(
    "OPTIMIZATION_IMPROVEMENT_WINDOW",
    10
)


# ============================================================================
# Review Agent Configuration
# ============================================================================

BASE_TOKEN_COUNT = get_env_int("BASE_TOKEN_COUNT", 1000)
COMPLEXITY_TOKEN_MULTIPLIER = get_env_int("COMPLEXITY_TOKEN_MULTIPLIER", 5000)
MAX_VERIFICATION_AGENTS = get_env_int("MAX_VERIFICATION_AGENTS", 10)


# ============================================================================
# Performance Requirements
# ============================================================================

LATENCY_REQUIREMENT_MS = get_env_int("LATENCY_REQUIREMENT_MS", 5000)


# ============================================================================
# Context Retrieval Configuration
# ============================================================================

CONTEXT_HISTORY_DAYS = get_env_int("CONTEXT_HISTORY_DAYS", 90)


# ============================================================================
# Storage Configuration
# ============================================================================

REVIEW_STORE_PATH = get_env_str("REVIEW_STORE_PATH", "./data/reviews")


# ============================================================================
# DeepWiki Integration Configuration
# ============================================================================

# DeepWiki MCP endpoints
DEEPWIKI_MCP_URL = get_env_str(
    "DEEPWIKI_MCP_URL",
    "https://mcp.deepwiki.com/mcp"
)
DEEPWIKI_SSE_URL = get_env_str(
    "DEEPWIKI_SSE_URL",
    "https://mcp.deepwiki.com/sse"
)

# DeepWiki feature flags and timeouts
DEEPWIKI_ENABLED = get_env_str("DEEPWIKI_ENABLED", "true").lower() in ("true", "1", "yes")
DEEPWIKI_TIMEOUT = get_env_int("DEEPWIKI_TIMEOUT", 30)
DEEPWIKI_CACHE_TTL = get_env_int("DEEPWIKI_CACHE_TTL", 3600)
DEEPWIKI_MAX_RETRIES = get_env_int("DEEPWIKI_MAX_RETRIES", 3)


# ============================================================================
# Devin Integration Configuration (for private repos)
# ============================================================================

# Devin API for private repository indexing
DEVIN_API_KEY = get_env_str("DEVIN_API_KEY", "")  # Empty = disabled
DEVIN_API_URL = get_env_str("DEVIN_API_URL", "https://api.devin.ai")
DEVIN_TIMEOUT = get_env_int("DEVIN_TIMEOUT", 30)
DEVIN_AUTO_REQUEST_INDEXING = get_env_str(
    "DEVIN_AUTO_REQUEST_INDEXING",
    "false"
).lower() in ("true", "1", "yes")


# ============================================================================
# Dependency Graph Configuration
# ============================================================================

# Graph caching and performance
GRAPH_CACHE_TTL = get_env_int("GRAPH_CACHE_TTL", 3600)
GRAPH_BUILD_TIMEOUT = get_env_int("GRAPH_BUILD_TIMEOUT", 60)
GRAPH_MAX_DEPTH = get_env_int("GRAPH_MAX_DEPTH", 10)

# Impact analysis thresholds
GRAPH_RISK_THRESHOLD_LOW = get_env_float("GRAPH_RISK_THRESHOLD_LOW", 0.05)
GRAPH_RISK_THRESHOLD_MEDIUM = get_env_float("GRAPH_RISK_THRESHOLD_MEDIUM", 0.15)
GRAPH_RISK_THRESHOLD_HIGH = get_env_float("GRAPH_RISK_THRESHOLD_HIGH", 0.30)


# ============================================================================
# AST-Grep Security Scanner Configuration
# ============================================================================

# Enable/disable ast-grep scanner
ASTGREP_ENABLED = get_env_str("ASTGREP_ENABLED", "true").lower() in ("true", "1", "yes")

# Rules repository configuration
ASTGREP_RULES_REPO = get_env_str("ASTGREP_RULES_REPO", "coderabbitai/ast-grep-essentials")
ASTGREP_RULES_PATH = get_env_str("ASTGREP_RULES_PATH", "/tmp/ast-grep-rules")

# Rule caching configuration
ASTGREP_CACHE_TTL = get_env_int("ASTGREP_CACHE_TTL", 86400)  # 24 hours
ASTGREP_AUTO_UPDATE = get_env_str("ASTGREP_AUTO_UPDATE", "true").lower() in ("true", "1", "yes")

# Scanning configuration
ASTGREP_SCAN_TIMEOUT = get_env_int("ASTGREP_SCAN_TIMEOUT", 30)  # Per-file timeout in seconds
ASTGREP_MAX_FINDINGS_PER_FILE = get_env_int("ASTGREP_MAX_FINDINGS_PER_FILE", 50)

# Security thresholds
SECURITY_BLOCK_ON_CRITICAL = get_env_str("SECURITY_BLOCK_ON_CRITICAL", "true").lower() in ("true", "1", "yes")
SECURITY_MAX_HIGH_SEVERITY = get_env_int("SECURITY_MAX_HIGH_SEVERITY", 3)
SECURITY_CONFIDENCE_THRESHOLD = get_env_float("SECURITY_CONFIDENCE_THRESHOLD", 0.7)


# ============================================================================
# HTTP Status Codes (for reference)
# ============================================================================

HTTP_STATUS_OK = 200
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_INTERNAL_ERROR = 500


# ============================================================================
# Configuration Export
# ============================================================================

def get_config_dict() -> dict:
    """Get all configuration as dictionary for inspection/debugging."""
    return {
        "service_urls": {
            "embedding_service": EMBEDDING_SERVICE_URL,
            "vector_search_service": VECTOR_SEARCH_SERVICE_URL,
        },
        "server": {
            "host": SERVER_HOST,
            "port": SERVER_PORT,
            "workers": SERVER_WORKERS,
        },
        "timeouts": {
            "http_request": HTTP_REQUEST_TIMEOUT,
            "static_analyzer": STATIC_ANALYZER_TIMEOUT,
            "agent_execution": AGENT_EXECUTION_TIMEOUT,
            "sandbox_execution": SANDBOX_EXECUTION_TIMEOUT,
        },
        "sandbox": {
            "max_memory_mb": SANDBOX_MAX_MEMORY_MB,
            "max_cpus": SANDBOX_MAX_CPUS,
            "max_output_size_bytes": SANDBOX_MAX_OUTPUT_SIZE_BYTES,
            "max_processes": SANDBOX_MAX_PROCESSES,
            "docker_image": SANDBOX_DOCKER_IMAGE,
        },
        "truncation_limits": {
            "error_output": TRUNCATE_ERROR_OUTPUT,
            "sandbox_output": TRUNCATE_SANDBOX_OUTPUT,
            "static_context": TRUNCATE_STATIC_CONTEXT,
            "code_changes": TRUNCATE_CODE_CHANGES,
            "verification_text": TRUNCATE_VERIFICATION_TEXT,
        },
        "batch_processing": {
            "embedding_batch_size": EMBEDDING_BATCH_SIZE,
            "default_top_k": DEFAULT_TOP_K_RESULTS,
        },
        "cache": {
            "ttl_seconds": CACHE_TTL_SECONDS,
            "max_size_mb": MAX_CACHE_SIZE_MB,
        },
        "optimization": {
            "max_candidates": MAX_OPTIMIZATION_CANDIDATES,
            "max_iterations": MAX_OPTIMIZATION_ITERATIONS,
            "eval_dataset_size": OPTIMIZATION_EVAL_DATASET_SIZE,
            "improvement_window": OPTIMIZATION_IMPROVEMENT_WINDOW,
        },
        "review": {
            "base_tokens": BASE_TOKEN_COUNT,
            "complexity_multiplier": COMPLEXITY_TOKEN_MULTIPLIER,
            "max_verification_agents": MAX_VERIFICATION_AGENTS,
        },
        "performance": {
            "latency_requirement_ms": LATENCY_REQUIREMENT_MS,
        },
        "context": {
            "history_days": CONTEXT_HISTORY_DAYS,
        },
        "storage": {
            "review_store_path": REVIEW_STORE_PATH,
        },
        "deepwiki": {
            "mcp_url": DEEPWIKI_MCP_URL,
            "sse_url": DEEPWIKI_SSE_URL,
            "enabled": DEEPWIKI_ENABLED,
            "timeout": DEEPWIKI_TIMEOUT,
            "cache_ttl": DEEPWIKI_CACHE_TTL,
            "max_retries": DEEPWIKI_MAX_RETRIES,
        },
        "devin": {
            "api_url": DEVIN_API_URL,
            "api_key_set": bool(DEVIN_API_KEY),  # Don't expose actual key
            "timeout": DEVIN_TIMEOUT,
            "auto_request_indexing": DEVIN_AUTO_REQUEST_INDEXING,
        },
        "graph": {
            "cache_ttl": GRAPH_CACHE_TTL,
            "build_timeout": GRAPH_BUILD_TIMEOUT,
            "max_depth": GRAPH_MAX_DEPTH,
            "risk_thresholds": {
                "low": GRAPH_RISK_THRESHOLD_LOW,
                "medium": GRAPH_RISK_THRESHOLD_MEDIUM,
                "high": GRAPH_RISK_THRESHOLD_HIGH,
            },
        },
        "astgrep": {
            "enabled": ASTGREP_ENABLED,
            "rules_repo": ASTGREP_RULES_REPO,
            "rules_path": ASTGREP_RULES_PATH,
            "cache_ttl": ASTGREP_CACHE_TTL,
            "auto_update": ASTGREP_AUTO_UPDATE,
            "scan_timeout": ASTGREP_SCAN_TIMEOUT,
            "max_findings_per_file": ASTGREP_MAX_FINDINGS_PER_FILE,
        },
        "security": {
            "block_on_critical": SECURITY_BLOCK_ON_CRITICAL,
            "max_high_severity": SECURITY_MAX_HIGH_SEVERITY,
            "confidence_threshold": SECURITY_CONFIDENCE_THRESHOLD,
        },
    }
