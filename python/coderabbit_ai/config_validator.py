"""Configuration validation module for CodeRabbit AI.

This module provides Pydantic-based validation for all configuration values,
ensuring type safety and clear error messages.
"""

from typing import Optional, List, Set, Literal
from pydantic import BaseModel, Field, validator, root_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import re


class ServiceConfig(BaseModel):
    """Service URL and network configuration."""
    
    embedding_service_url: str = Field(
        default="http://localhost:8081/embed",
        description="URL for embedding service"
    )
    
    vector_search_service_url: str = Field(
        default="http://localhost:8082/search",
        description="URL for vector search service"
    )
    
    @validator("embedding_service_url", "vector_search_service_url")
    def validate_url(cls, v):
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL format: {v}")
        return v


class ServerConfig(BaseModel):
    """Server configuration."""
    
    host: str = Field(default="127.0.0.1", ge=1, le=254)
    port: int = Field(default=8081, ge=1, le=65535)
    workers: int = Field(default=1, ge=1, le=32)


class TimeoutConfig(BaseModel):
    """Timeout configuration."""
    
    http_request_timeout: int = Field(default=10, ge=1, le=300)
    static_analyzer_timeout: int = Field(default=30, ge=5, le=300)
    agent_execution_timeout: int = Field(default=300, ge=10, le=3600)
    sandbox_execution_timeout: int = Field(default=30, ge=5, le=300)


class SandboxConfig(BaseModel):
    """Sandbox execution configuration."""
    
    max_memory_mb: int = Field(default=512, ge=128, le=8192)
    max_cpus: float = Field(default=1.0, ge=0.1, le=8.0)
    max_output_size_bytes: int = Field(default=1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    max_processes: int = Field(default=50, ge=1, le=1000)
    docker_image: str = Field(default="coderabbit-sandbox:latest")


class TextProcessingConfig(BaseModel):
    """Text processing and truncation limits."""
    
    truncate_error_output: int = Field(default=1000, ge=100, le=10000)
    truncate_sandbox_output: int = Field(default=1000, ge=100, le=10000)
    truncate_static_context: int = Field(default=1000, ge=100, le=10000)
    truncate_code_changes: int = Field(default=5000, ge=500, le=50000)
    truncate_verification_text: int = Field(default=6000, ge=500, le=60000)


class BatchProcessingConfig(BaseModel):
    """Batch processing configuration."""
    
    embedding_batch_size: int = Field(default=32, ge=1, le=128)
    default_top_k_results: int = Field(default=5, ge=1, le=50)


class CacheConfig(BaseModel):
    """Cache configuration."""
    
    cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    max_cache_size_mb: int = Field(default=1024, ge=64, le=10240)


class OptimizationConfig(BaseModel):
    """Optimization configuration."""
    
    max_optimization_candidates: int = Field(default=50, ge=10, le=500)
    max_optimization_iterations: int = Field(default=100, ge=10, le=1000)
    optimization_eval_dataset_size: int = Field(default=200, ge=50, le=1000)
    optimization_improvement_window: int = Field(default=10, ge=5, le=50)


class ReviewConfig(BaseModel):
    """Review agent configuration."""
    
    base_token_count: int = Field(default=1000, ge=500, le=10000)
    complexity_token_multiplier: int = Field(default=5000, ge=1000, le=20000)
    max_verification_agents: int = Field(default=10, ge=1, le=50)


class PerformanceConfig(BaseModel):
    """Performance requirements."""
    
    latency_requirement_ms: int = Field(default=5000, ge=1000, le=60000)


class ContextConfig(BaseModel):
    """Context retrieval configuration."""
    
    context_history_days: int = Field(default=90, ge=1, le=365)


class StorageConfig(BaseModel):
    """Storage configuration."""
    
    review_store_path: str = Field(default="./data/reviews")
    
    @validator("review_store_path")
    def validate_path(cls, v):
        """Validate path format."""
        if not os.path.isabs(v) and not v.startswith("./"):
            raise ValueError(f"Invalid path format: {v}")
        return v


class DeepWikiConfig(BaseModel):
    """DeepWiki integration configuration."""
    
    mcp_url: str = Field(default="https://mcp.deepwiki.com/mcp")
    sse_url: str = Field(default="https://mcp.deepwiki.com/sse")
    enabled: bool = True
    timeout: int = Field(default=30, ge=5, le=300)
    cache_ttl: int = Field(default=3600, ge=60, le=86400)
    max_retries: int = Field(default=3, ge=1, le=10)
    
    @validator("mcp_url", "sse_url")
    def validate_url(cls, v):
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL format: {v}")
        return v


class DevinConfig(BaseModel):
    """Devin integration configuration."""
    
    api_url: str = Field(default="https://api.devin.ai")
    api_key: Optional[str] = Field(default="", min_length=0)
    timeout: int = Field(default=30, ge=5, le=300)
    auto_request_indexing: bool = False
    
    @validator("api_url")
    def validate_url(cls, v):
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL format: {v}")
        return v


class GraphConfig(BaseModel):
    """Dependency graph configuration."""
    
    cache_ttl: int = Field(default=3600, ge=60, le=86400)
    build_timeout: int = Field(default=60, ge=10, le=600)
    max_depth: int = Field(default=10, ge=5, le=50)
    risk_threshold_low: float = Field(default=0.05, ge=0.0, le=1.0)
    risk_threshold_medium: float = Field(default=0.15, ge=0.0, le=1.0)
    risk_threshold_high: float = Field(default=0.30, ge=0.0, le=1.0)
    
    @root_validator
    def validate_thresholds(cls, values):
        """Validate risk thresholds are in ascending order."""
        low = values.get("risk_threshold_low", 0)
        medium = values.get("risk_threshold_medium", 0)
        high = values.get("risk_threshold_high", 0)
        
        if not (low < medium < high):
            raise ValueError(
                f"Risk thresholds must be in ascending order: {low} < {medium} < {high}"
            )
        return values


class AstGrepConfig(BaseModel):
    """AST-Grep security scanner configuration."""
    
    enabled: bool = True
    rules_repo: str = Field(default="coderabbitai/ast-grep-essentials")
    rules_path: str = Field(default="/tmp/ast-grep-rules")
    cache_ttl: int = Field(default=86400, ge=3600, le=604800)
    auto_update: bool = True
    scan_timeout: int = Field(default=30, ge=5, le=300)
    max_findings_per_file: int = Field(default=50, ge=1, le=500)


class SemgrepConfig(BaseModel):
    """Semgrep security scanner configuration."""
    
    enabled: bool = False
    rulesets: str = Field(default="auto")
    timeout: int = Field(default=60, ge=10, le=600)
    max_findings_per_file: int = Field(default=50, ge=1, le=500)


class SecurityThresholdsConfig(BaseModel):
    """Security thresholds for all scanners."""
    
    block_on_critical: bool = True
    max_high_severity: int = Field(default=3, ge=0, le=100)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class FeatureFlags(BaseModel):
    """Feature flags configuration."""
    
    enable_security_scanning: bool = True
    enable_ai_review: bool = True
    enable_vector_search: bool = True
    enable_metrics: bool = True
    enable_pr_test_runner: bool = False
    enable_deepwiki: bool = True
    enable_devin: bool = False


class ConfigValidator(BaseModel):
    """Comprehensive configuration validator."""
    
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    text_processing: TextProcessingConfig = Field(default_factory=TextProcessingConfig)
    batch_processing: BatchProcessingConfig = Field(default_factory=BatchProcessingConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    deepwiki: DeepWikiConfig = Field(default_factory=DeepWikiConfig)
    devin: DevinConfig = Field(default_factory=DevinConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    astgrep: AstGrepConfig = Field(default_factory=AstGrepConfig)
    semgrep: SemgrepConfig = Field(default_factory=SemgrepConfig)
    security: SecurityThresholdsConfig = Field(default_factory=SecurityThresholdsConfig)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)
    
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    
    def validate_production_hardening(self) -> List[str]:
        """Validate production-specific security hardening.
        
        Returns:
            List of warnings/errors found.
        """
        warnings = []
        
        if self.environment == "production":
            if self.devin.api_key and len(self.devin.api_key) < 20:
                warnings.append("SECURITY: DEVIN_API_KEY appears too short")
            
            if self.sandbox.max_memory_mb < 256:
                warnings.append("PERFORMANCE: Sandbox max memory may be too low for production")
            
            if self.timeouts.http_request_timeout < 30:
                warnings.append("PERFORMANCE: HTTP request timeout may be too low for production")
            
            if not self.security.block_on_critical:
                warnings.append("SECURITY: BLOCK_ON_CRITICAL disabled in production")
            
            if self.feature_flags.enable_pr_test_runner and not self.sandbox.max_cpus >= 2.0:
                warnings.append("PERFORMANCE: PR test runner enabled but sandbox has limited CPU")
        
        return warnings
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary for inspection."""
        return {
            "service": self.service.dict(),
            "server": self.server.dict(),
            "timeouts": self.timeouts.dict(),
            "sandbox": self.sandbox.dict(),
            "text_processing": self.text_processing.dict(),
            "batch_processing": self.batch_processing.dict(),
            "cache": self.cache.dict(),
            "optimization": self.optimization.dict(),
            "review": self.review.dict(),
            "performance": self.performance.dict(),
            "context": self.context.dict(),
            "storage": self.storage.dict(),
            "deepwiki": self.deepwiki.dict(),
            "devin": self.devin.dict(exclude={"api_key"}),
            "graph": self.graph.dict(),
            "astgrep": self.astgrep.dict(),
            "semgrep": self.semgrep.dict(),
            "security": self.security.dict(),
            "feature_flags": self.feature_flags.dict(),
            "environment": self.environment,
            "log_level": self.log_level,
        }


def validate_config_from_env() -> ConfigValidator:
    """Load and validate configuration from environment variables.
    
    Returns:
        Validated ConfigValidator instance.
    """
    config_dict = {
        "service": {
            "embedding_service_url": os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8081/embed"),
            "vector_search_service_url": os.getenv("VECTOR_SEARCH_SERVICE_URL", "http://localhost:8082/search"),
        },
        "server": {
            "host": os.getenv("HOST", "127.0.0.1"),
            "port": int(os.getenv("PORT", "8081")),
            "workers": int(os.getenv("WORKERS", "1")),
        },
        "timeouts": {
            "http_request_timeout": int(os.getenv("HTTP_REQUEST_TIMEOUT", "10")),
            "static_analyzer_timeout": int(os.getenv("STATIC_ANALYZER_TIMEOUT", "30")),
            "agent_execution_timeout": int(os.getenv("AGENT_EXECUTION_TIMEOUT", "300")),
            "sandbox_execution_timeout": int(os.getenv("SANDBOX_EXECUTION_TIMEOUT", "30")),
        },
        "sandbox": {
            "max_memory_mb": int(os.getenv("SANDBOX_MAX_MEMORY_MB", "512")),
            "max_cpus": float(os.getenv("SANDBOX_MAX_CPUS", "1.0")),
            "max_output_size_bytes": int(os.getenv("SANDBOX_MAX_OUTPUT_SIZE_BYTES", str(1024 * 1024))),
            "max_processes": int(os.getenv("SANDBOX_MAX_PROCESSES", "50")),
            "docker_image": os.getenv("SANDBOX_DOCKER_IMAGE", "coderabbit-sandbox:latest"),
        },
        "text_processing": {
            "truncate_error_output": int(os.getenv("TRUNCATE_ERROR_OUTPUT", "1000")),
            "truncate_sandbox_output": int(os.getenv("TRUNCATE_SANDBOX_OUTPUT", "1000")),
            "truncate_static_context": int(os.getenv("TRUNCATE_STATIC_CONTEXT", "1000")),
            "truncate_code_changes": int(os.getenv("TRUNCATE_CODE_CHANGES", "5000")),
            "truncate_verification_text": int(os.getenv("TRUNCATE_VERIFICATION_TEXT", "6000")),
        },
        "batch_processing": {
            "embedding_batch_size": int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
            "default_top_k_results": int(os.getenv("DEFAULT_TOP_K_RESULTS", "5")),
        },
        "cache": {
            "cache_ttl_seconds": int(os.getenv("CACHE_TTL_SECONDS", "3600")),
            "max_cache_size_mb": int(os.getenv("MAX_CACHE_SIZE_MB", "1024")),
        },
        "optimization": {
            "max_optimization_candidates": int(os.getenv("MAX_OPTIMIZATION_CANDIDATES", "50")),
            "max_optimization_iterations": int(os.getenv("MAX_OPTIMIZATION_ITERATIONS", "100")),
            "optimization_eval_dataset_size": int(os.getenv("OPTIMIZATION_EVAL_DATASET_SIZE", "200")),
            "optimization_improvement_window": int(os.getenv("OPTIMIZATION_IMPROVEMENT_WINDOW", "10")),
        },
        "review": {
            "base_token_count": int(os.getenv("BASE_TOKEN_COUNT", "1000")),
            "complexity_token_multiplier": int(os.getenv("COMPLEXITY_TOKEN_MULTIPLIER", "5000")),
            "max_verification_agents": int(os.getenv("MAX_VERIFICATION_AGENTS", "10")),
        },
        "performance": {
            "latency_requirement_ms": int(os.getenv("LATENCY_REQUIREMENT_MS", "5000")),
        },
        "context": {
            "context_history_days": int(os.getenv("CONTEXT_HISTORY_DAYS", "90")),
        },
        "storage": {
            "review_store_path": os.getenv("REVIEW_STORE_PATH", "./data/reviews"),
        },
        "deepwiki": {
            "mcp_url": os.getenv("DEEPWIKI_MCP_URL", "https://mcp.deepwiki.com/mcp"),
            "sse_url": os.getenv("DEEPWIKI_SSE_URL", "https://mcp.deepwiki.com/sse"),
            "enabled": os.getenv("DEEPWIKI_ENABLED", "true").lower() in ("true", "1", "yes"),
            "timeout": int(os.getenv("DEEPWIKI_TIMEOUT", "30")),
            "cache_ttl": int(os.getenv("DEEPWIKI_CACHE_TTL", "3600")),
            "max_retries": int(os.getenv("DEEPWIKI_MAX_RETRIES", "3")),
        },
        "devin": {
            "api_url": os.getenv("DEVIN_API_URL", "https://api.devin.ai"),
            "api_key": os.getenv("DEVIN_API_KEY", ""),
            "timeout": int(os.getenv("DEVIN_TIMEOUT", "30")),
            "auto_request_indexing": os.getenv("DEVIN_AUTO_REQUEST_INDEXING", "false").lower() in ("true", "1", "yes"),
        },
        "graph": {
            "cache_ttl": int(os.getenv("GRAPH_CACHE_TTL", "3600")),
            "build_timeout": int(os.getenv("GRAPH_BUILD_TIMEOUT", "60")),
            "max_depth": int(os.getenv("GRAPH_MAX_DEPTH", "10")),
            "risk_threshold_low": float(os.getenv("GRAPH_RISK_THRESHOLD_LOW", "0.05")),
            "risk_threshold_medium": float(os.getenv("GRAPH_RISK_THRESHOLD_MEDIUM", "0.15")),
            "risk_threshold_high": float(os.getenv("GRAPH_RISK_THRESHOLD_HIGH", "0.30")),
        },
        "astgrep": {
            "enabled": os.getenv("ASTGREP_ENABLED", "true").lower() in ("true", "1", "yes"),
            "rules_repo": os.getenv("ASTGREP_RULES_REPO", "coderabbitai/ast-grep-essentials"),
            "rules_path": os.getenv("ASTGREP_RULES_PATH", "/tmp/ast-grep-rules"),
            "cache_ttl": int(os.getenv("ASTGREP_CACHE_TTL", "86400")),
            "auto_update": os.getenv("ASTGREP_AUTO_UPDATE", "true").lower() in ("true", "1", "yes"),
            "scan_timeout": int(os.getenv("ASTGREP_SCAN_TIMEOUT", "30")),
            "max_findings_per_file": int(os.getenv("ASTGREP_MAX_FINDINGS_PER_FILE", "50")),
        },
        "semgrep": {
            "enabled": os.getenv("SEMGREP_ENABLED", "false").lower() in ("true", "1", "yes"),
            "rulesets": os.getenv("SEMGREP_RULESETS", "auto"),
            "timeout": int(os.getenv("SEMGREP_TIMEOUT", "60")),
            "max_findings_per_file": int(os.getenv("SEMGREP_MAX_FINDINGS_PER_FILE", "50")),
        },
        "security": {
            "block_on_critical": os.getenv("SECURITY_BLOCK_ON_CRITICAL", "true").lower() in ("true", "1", "yes"),
            "max_high_severity": int(os.getenv("SECURITY_MAX_HIGH_SEVERITY", "3")),
            "confidence_threshold": float(os.getenv("SECURITY_CONFIDENCE_THRESHOLD", "0.7")),
        },
        "feature_flags": {
            "enable_security_scanning": os.getenv("ENABLE_SECURITY_SCANNING", "true").lower() in ("true", "1", "yes"),
            "enable_ai_review": os.getenv("ENABLE_AI_REVIEW", "true").lower() in ("true", "1", "yes"),
            "enable_vector_search": os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() in ("true", "1", "yes"),
            "enable_metrics": os.getenv("ENABLE_METRICS", "true").lower() in ("true", "1", "yes"),
            "enable_pr_test_runner": os.getenv("ENABLE_PR_TEST_RUNNER", "false").lower() in ("true", "1", "yes"),
            "enable_deepwiki": os.getenv("ENABLE_DEEPWIKI", "true").lower() in ("true", "1", "yes"),
            "enable_devin": os.getenv("ENABLE_DEVIN", "false").lower() in ("true", "1", "yes"),
        },
        "environment": os.getenv("ENVIRONMENT", "development"),
        "log_level": os.getenv("LOG_LEVEL", "info"),
    }
    
    return ConfigValidator(**config_dict)


__all__ = [
    "ConfigValidator",
    "validate_config_from_env",
    "ServiceConfig",
    "ServerConfig",
    "TimeoutConfig",
    "SandboxConfig",
    "TextProcessingConfig",
    "BatchProcessingConfig",
    "CacheConfig",
    "OptimizationConfig",
    "ReviewConfig",
    "PerformanceConfig",
    "ContextConfig",
    "StorageConfig",
    "DeepWikiConfig",
    "DevinConfig",
    "GraphConfig",
    "AstGrepConfig",
    "SemgrepConfig",
    "SecurityThresholdsConfig",
    "FeatureFlags",
]
