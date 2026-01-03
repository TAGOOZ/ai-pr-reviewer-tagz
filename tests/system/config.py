"""Test configuration for system integration tests."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TestConfig:
    """Configuration for system integration tests."""

    # Service URLs
    api_gateway_url: str = field(
        default_factory=lambda: os.getenv("API_GATEWAY_URL", "http://localhost:8080")
    )
    ai_pipeline_url: str = field(
        default_factory=lambda: os.getenv("AI_PIPELINE_URL", "http://localhost:8000")
    )

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://postgres.sskoefvbzqfxjyzndtzr:Coderabbit123%40@aws-1-eu-west-1.pooler.supabase.com:5432/postgres",
        )
    )

    # Redis
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379")
    )

    # GitHub
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    github_webhook_secret: str = field(
        default_factory=lambda: os.getenv("GITHUB_WEBHOOK_SECRET", "test_secret")
    )
    test_repo: str = field(
        default_factory=lambda: os.getenv("TEST_REPO", "tagz97/ai-pr-reviewer")
    )

    # Vector DB
    lancedb_path: str = field(
        default_factory=lambda: os.getenv("LANCEDB_PATH", "./data/lancedb")
    )
    embedding_dimension: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIMENSION", "384"))
    )

    # Timeouts (seconds)
    timeout_health: int = 30
    timeout_analysis: int = 60
    timeout_review: int = 300
    timeout_http: int = 30

    # Load test settings
    run_load_tests: bool = False
    load_test_duration: int = 60
    concurrent_requests: int = 100
    simultaneous_reviews: int = 5

    # Test behavior
    skip_ai_tests: bool = field(
        default_factory=lambda: os.getenv("SKIP_AI_TESTS", "false").lower() == "true"
    )
    use_mocks: bool = field(
        default_factory=lambda: os.getenv("USE_MOCKS", "false").lower() == "true"
    )
    verbose: bool = field(
        default_factory=lambda: os.getenv("VERBOSE", "true").lower() == "true"
    )


def get_config() -> TestConfig:
    """Get test configuration from environment."""
    return TestConfig()
