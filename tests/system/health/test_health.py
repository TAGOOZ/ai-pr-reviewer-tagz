"""Health check tests for all system components."""

import asyncio
from typing import Tuple

import httpx
import asyncpg
import redis.asyncio as aioredis

from ..config import TestConfig
from ..issue_collector import IssueCollector, Severity, Category


async def test_api_gateway_health(config: TestConfig, collector: IssueCollector) -> bool:
    """Test API Gateway health endpoint."""
    try:
        async with httpx.AsyncClient(timeout=config.timeout_health) as client:
            response = await client.get(f"{config.api_gateway_url}/health")
            if response.status_code == 200:
                collector.add_log(f"API Gateway health check passed: {response.status_code}")
                return True
            else:
                collector.record_issue(
                    test_name="test_api_gateway_health",
                    component="api_gateway",
                    message=f"Health check returned status {response.status_code}",
                    severity=Severity.HIGH,
                    category=Category.HEALTH,
                    context={"status_code": response.status_code, "body": response.text[:500]}
                )
                return False
    except httpx.ConnectError as e:
        collector.record_failure(
            test_name="test_api_gateway_health",
            component="api_gateway",
            error=e,
            severity=Severity.CRITICAL,
            category=Category.CONNECTIVITY,
            context={"url": config.api_gateway_url}
        )
        return False
    except Exception as e:
        collector.record_failure(
            test_name="test_api_gateway_health",
            component="api_gateway",
            error=e,
            severity=Severity.CRITICAL,
            category=Category.HEALTH
        )
        return False


async def test_python_service_health(config: TestConfig, collector: IssueCollector) -> bool:
    """Test Python AI Pipeline health endpoint."""
    try:
        async with httpx.AsyncClient(timeout=config.timeout_health) as client:
            response = await client.get(f"{config.ai_pipeline_url}/health")
            if response.status_code == 200:
                collector.add_log(f"Python service health check passed: {response.status_code}")
                return True
            else:
                collector.record_issue(
                    test_name="test_python_service_health",
                    component="ai_pipeline",
                    message=f"Health check returned status {response.status_code}",
                    severity=Severity.HIGH,
                    category=Category.HEALTH,
                    context={"status_code": response.status_code}
                )
                return False
    except httpx.ConnectError as e:
        collector.record_failure(
            test_name="test_python_service_health",
            component="ai_pipeline",
            error=e,
            severity=Severity.CRITICAL,
            category=Category.CONNECTIVITY,
            context={"url": config.ai_pipeline_url}
        )
        return False
    except Exception as e:
        collector.record_failure(
            test_name="test_python_service_health",
            component="ai_pipeline",
            error=e,
            severity=Severity.CRITICAL,
            category=Category.HEALTH
        )
        return False


async def test_database_connectivity(config: TestConfig, collector: IssueCollector) -> bool:
    """Test PostgreSQL database connectivity."""
    try:
        conn = await asyncpg.connect(config.database_url, timeout=config.timeout_health)
        result = await conn.fetchval("SELECT 1")
        await conn.close()
        
        if result == 1:
            collector.add_log("Database connectivity check passed")
            return True
        else:
            collector.record_issue(
                test_name="test_database_connectivity",
                component="database",
                message=f"Unexpected query result: {result}",
                severity=Severity.HIGH,
                category=Category.CONNECTIVITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_database_connectivity",
            component="database",
            error=e,
            severity=Severity.CRITICAL,
            category=Category.CONNECTIVITY,
            context={"database_url": config.database_url[:30] + "..."}
        )
        return False


async def test_database_schema(config: TestConfig, collector: IssueCollector) -> bool:
    """Test that required database tables exist."""
    required_tables = [
        "organizations", "repositories", "users", "pull_requests",
        "file_changes", "jobs", "job_progress", "analysis_results",
        "vector_index", "review_comments", "ai_models", "dspy_signatures"
    ]
    
    try:
        conn = await asyncpg.connect(config.database_url, timeout=config.timeout_health)
        
        # Get all tables
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        existing_tables = {row['table_name'] for row in tables}
        await conn.close()
        
        missing = set(required_tables) - existing_tables
        if missing:
            collector.record_issue(
                test_name="test_database_schema",
                component="database",
                message=f"Missing tables: {', '.join(missing)}",
                severity=Severity.HIGH,
                category=Category.DATA_INTEGRITY,
                context={"missing_tables": list(missing), "existing_tables": list(existing_tables)}
            )
            return False
        
        collector.add_log(f"Database schema check passed: {len(existing_tables)} tables found")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_database_schema",
            component="database",
            error=e,
            severity=Severity.HIGH,
            category=Category.DATA_INTEGRITY
        )
        return False


async def test_redis_connectivity(config: TestConfig, collector: IssueCollector) -> bool:
    """Test Redis connectivity."""
    try:
        redis_client = aioredis.from_url(config.redis_url)
        result = await redis_client.ping()
        await redis_client.close()
        
        if result:
            collector.add_log("Redis connectivity check passed")
            return True
        else:
            collector.record_issue(
                test_name="test_redis_connectivity",
                component="redis",
                message="Redis PING returned False",
                severity=Severity.HIGH,
                category=Category.CONNECTIVITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_redis_connectivity",
            component="redis",
            error=e,
            severity=Severity.HIGH,
            category=Category.CONNECTIVITY,
            context={"redis_url": config.redis_url}
        )
        return False


async def test_redis_operations(config: TestConfig, collector: IssueCollector) -> bool:
    """Test basic Redis operations."""
    try:
        redis_client = aioredis.from_url(config.redis_url)
        
        # Test set/get
        test_key = "system_test:health_check"
        test_value = "test_value_123"
        
        await redis_client.set(test_key, test_value, ex=60)
        result = await redis_client.get(test_key)
        await redis_client.delete(test_key)
        await redis_client.close()
        
        if result and result.decode() == test_value:
            collector.add_log("Redis operations check passed")
            return True
        else:
            collector.record_issue(
                test_name="test_redis_operations",
                component="redis",
                message=f"Redis get returned unexpected value: {result}",
                severity=Severity.MEDIUM,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_redis_operations",
            component="redis",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def run_all(config: TestConfig, collector: IssueCollector) -> Tuple[int, int, int]:
    """Run all health tests and return (passed, failed, skipped)."""
    tests = [
        ("API Gateway Health", test_api_gateway_health),
        ("Python Service Health", test_python_service_health),
        ("Database Connectivity", test_database_connectivity),
        ("Database Schema", test_database_schema),
        ("Redis Connectivity", test_redis_connectivity),
        ("Redis Operations", test_redis_operations),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, test_func in tests:
        try:
            result = await test_func(config, collector)
            if result:
                passed += 1
                print(f"    ✅ {name}")
            else:
                failed += 1
                print(f"    ❌ {name}")
        except Exception as e:
            failed += 1
            print(f"    ❌ {name}: {str(e)[:50]}")
            collector.record_failure(
                test_name=name,
                component="health",
                error=e,
                severity=Severity.HIGH,
                category=Category.UNKNOWN
            )
    
    return passed, failed, skipped
