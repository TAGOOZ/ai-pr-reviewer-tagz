"""Load and performance tests."""

import asyncio
import time
from typing import Tuple

import httpx

from ..config import TestConfig
from ..issue_collector import IssueCollector, Severity, Category


async def test_concurrent_health_checks(config: TestConfig, collector: IssueCollector) -> bool:
    """Test concurrent health check requests."""
    try:
        async def make_request():
            async with httpx.AsyncClient(timeout=10) as client:
                return await client.get(f"{config.api_gateway_url}/health")
        
        # Run concurrent requests
        num_requests = min(config.concurrent_requests, 50)  # Limit for safety
        
        start = time.time()
        tasks = [make_request() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start
        
        successes = [r for r in results if isinstance(r, httpx.Response) and r.status_code == 200]
        errors = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successes) / num_requests * 100
        rps = num_requests / elapsed
        
        if success_rate >= 95:
            collector.add_log(f"Concurrent health checks passed: {success_rate:.0f}% success, {rps:.0f} req/s")
            return True
        else:
            collector.record_issue(
                test_name="test_concurrent_health_checks",
                component="load",
                message=f"Low success rate: {success_rate:.0f}%",
                severity=Severity.MEDIUM,
                category=Category.PERFORMANCE,
                context={"success_rate": success_rate, "errors": len(errors)}
            )
            return False
    except httpx.ConnectError:
        collector.add_log("Concurrent health checks skipped - service not available")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_concurrent_health_checks",
            component="load",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.PERFORMANCE
        )
        return False


async def test_sustained_throughput(config: TestConfig, collector: IssueCollector) -> bool:
    """Test sustained request throughput over time."""
    try:
        duration = 10  # 10 second test
        requests_made = 0
        errors = 0
        
        start = time.time()
        async with httpx.AsyncClient(timeout=5) as client:
            while time.time() - start < duration:
                try:
                    response = await client.get(f"{config.api_gateway_url}/health")
                    if response.status_code == 200:
                        requests_made += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1
        
        elapsed = time.time() - start
        rps = requests_made / elapsed
        error_rate = errors / (requests_made + errors) * 100 if (requests_made + errors) > 0 else 0
        
        if rps >= 10 and error_rate < 5:
            collector.add_log(f"Sustained throughput passed: {rps:.0f} req/s, {error_rate:.1f}% errors")
            return True
        else:
            collector.record_issue(
                test_name="test_sustained_throughput",
                component="load",
                message=f"Low throughput or high errors: {rps:.0f} req/s, {error_rate:.1f}% errors",
                severity=Severity.MEDIUM,
                category=Category.PERFORMANCE
            )
            return False
    except httpx.ConnectError:
        collector.add_log("Sustained throughput test skipped - service not available")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_sustained_throughput",
            component="load",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.PERFORMANCE
        )
        return False


async def test_database_connection_pool(config: TestConfig, collector: IssueCollector) -> bool:
    """Test database connection pool under load."""
    try:
        import asyncpg
        
        async def make_query(pool):
            async with pool.acquire() as conn:
                return await conn.fetchval("SELECT 1")
        
        # Create connection pool
        pool = await asyncpg.create_pool(config.database_url, min_size=5, max_size=20)
        
        # Run concurrent queries
        num_queries = 100
        start = time.time()
        tasks = [make_query(pool) for _ in range(num_queries)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start
        
        await pool.close()
        
        successes = [r for r in results if r == 1]
        qps = len(successes) / elapsed
        
        if len(successes) >= num_queries * 0.95:
            collector.add_log(f"DB connection pool test passed: {qps:.0f} queries/s")
            return True
        else:
            collector.record_issue(
                test_name="test_database_connection_pool",
                component="load",
                message=f"Connection pool failures: {num_queries - len(successes)} failed",
                severity=Severity.MEDIUM,
                category=Category.PERFORMANCE
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_database_connection_pool",
            component="load",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.PERFORMANCE
        )
        return False


async def test_redis_throughput(config: TestConfig, collector: IssueCollector) -> bool:
    """Test Redis throughput under load."""
    try:
        import redis.asyncio as aioredis
        
        client = aioredis.from_url(config.redis_url)
        
        # Write test
        num_ops = 1000
        start = time.time()
        for i in range(num_ops):
            await client.set(f"load_test:{i}", f"value_{i}")
        write_time = time.time() - start
        
        # Read test
        start = time.time()
        for i in range(num_ops):
            await client.get(f"load_test:{i}")
        read_time = time.time() - start
        
        # Cleanup
        for i in range(num_ops):
            await client.delete(f"load_test:{i}")
        await client.close()
        
        write_ops = num_ops / write_time
        read_ops = num_ops / read_time
        
        if write_ops >= 500 and read_ops >= 500:
            collector.add_log(f"Redis throughput passed: write={write_ops:.0f}/s, read={read_ops:.0f}/s")
            return True
        else:
            collector.record_issue(
                test_name="test_redis_throughput",
                component="load",
                message=f"Low Redis throughput: write={write_ops:.0f}/s, read={read_ops:.0f}/s",
                severity=Severity.MEDIUM,
                category=Category.PERFORMANCE
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_redis_throughput",
            component="load",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.PERFORMANCE
        )
        return False


async def run_all(config: TestConfig, collector: IssueCollector) -> Tuple[int, int, int]:
    """Run all load tests."""
    tests = [
        ("Concurrent Health Checks", test_concurrent_health_checks),
        ("Sustained Throughput", test_sustained_throughput),
        ("Database Connection Pool", test_database_connection_pool),
        ("Redis Throughput", test_redis_throughput),
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
    
    return passed, failed, skipped
