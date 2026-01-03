"""Tests for cache layer functionality."""

import json
import time
import uuid
from typing import Tuple

import redis.asyncio as aioredis

from ..config import TestConfig
from ..issue_collector import IssueCollector, Severity, Category


async def test_redis_set_get(config: TestConfig, collector: IssueCollector) -> bool:
    """Test basic Redis set/get operations."""
    try:
        client = aioredis.from_url(config.redis_url)
        
        key = f"test:cache:{uuid.uuid4()}"
        value = {"data": "test_value", "number": 42, "nested": {"a": 1}}
        
        # Set with TTL
        await client.set(key, json.dumps(value), ex=60)
        
        # Get
        result = await client.get(key)
        parsed = json.loads(result)
        
        # Cleanup
        await client.delete(key)
        await client.close()
        
        if parsed == value:
            collector.add_log("Redis set/get test passed")
            return True
        else:
            collector.record_issue(
                test_name="test_redis_set_get",
                component="cache",
                message="Redis value mismatch",
                severity=Severity.HIGH,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_redis_set_get",
            component="cache",
            error=e,
            severity=Severity.HIGH,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_redis_ttl(config: TestConfig, collector: IssueCollector) -> bool:
    """Test Redis TTL functionality."""
    try:
        client = aioredis.from_url(config.redis_url)
        
        key = f"test:ttl:{uuid.uuid4()}"
        
        # Set with 2 second TTL
        await client.set(key, "ttl_test", ex=2)
        
        # Check TTL
        ttl = await client.ttl(key)
        
        # Cleanup
        await client.delete(key)
        await client.close()
        
        if ttl > 0 and ttl <= 2:
            collector.add_log(f"Redis TTL test passed: ttl={ttl}")
            return True
        else:
            collector.record_issue(
                test_name="test_redis_ttl",
                component="cache",
                message=f"Unexpected TTL value: {ttl}",
                severity=Severity.MEDIUM,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_redis_ttl",
            component="cache",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_redis_hash_operations(config: TestConfig, collector: IssueCollector) -> bool:
    """Test Redis hash operations for structured data."""
    try:
        client = aioredis.from_url(config.redis_url)
        
        key = f"test:hash:{uuid.uuid4()}"
        
        # Set hash fields
        await client.hset(key, mapping={
            "field1": "value1",
            "field2": "value2",
            "count": "42"
        })
        
        # Get all fields
        result = await client.hgetall(key)
        
        # Cleanup
        await client.delete(key)
        await client.close()
        
        # Decode bytes to strings
        decoded = {k.decode(): v.decode() for k, v in result.items()}
        
        if decoded.get("field1") == "value1" and decoded.get("count") == "42":
            collector.add_log("Redis hash operations test passed")
            return True
        else:
            collector.record_issue(
                test_name="test_redis_hash_operations",
                component="cache",
                message=f"Hash data mismatch: {decoded}",
                severity=Severity.MEDIUM,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_redis_hash_operations",
            component="cache",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_redis_list_operations(config: TestConfig, collector: IssueCollector) -> bool:
    """Test Redis list operations for job queues."""
    try:
        client = aioredis.from_url(config.redis_url)
        
        key = f"test:queue:{uuid.uuid4()}"
        
        # Push items
        await client.rpush(key, "job1", "job2", "job3")
        
        # Get length
        length = await client.llen(key)
        
        # Pop item
        item = await client.lpop(key)
        
        # Cleanup
        await client.delete(key)
        await client.close()
        
        if length == 3 and item.decode() == "job1":
            collector.add_log("Redis list operations test passed")
            return True
        else:
            collector.record_issue(
                test_name="test_redis_list_operations",
                component="cache",
                message=f"List operations failed: length={length}, item={item}",
                severity=Severity.MEDIUM,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_redis_list_operations",
            component="cache",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_cache_latency(config: TestConfig, collector: IssueCollector) -> bool:
    """Test cache operation latency."""
    try:
        client = aioredis.from_url(config.redis_url)
        
        key = f"test:latency:{uuid.uuid4()}"
        value = "x" * 1000  # 1KB value
        
        # Measure set latency
        iterations = 100
        
        start = time.time()
        for i in range(iterations):
            await client.set(f"{key}:{i}", value)
        set_time = (time.time() - start) / iterations * 1000  # ms
        
        # Measure get latency
        start = time.time()
        for i in range(iterations):
            await client.get(f"{key}:{i}")
        get_time = (time.time() - start) / iterations * 1000  # ms
        
        # Cleanup
        for i in range(iterations):
            await client.delete(f"{key}:{i}")
        await client.close()
        
        # Check latency requirements (< 5ms for Redis)
        if set_time < 10 and get_time < 10:
            collector.add_log(f"Cache latency test passed: set={set_time:.2f}ms, get={get_time:.2f}ms")
            return True
        else:
            collector.record_issue(
                test_name="test_cache_latency",
                component="cache",
                message=f"High cache latency: set={set_time:.2f}ms, get={get_time:.2f}ms",
                severity=Severity.MEDIUM,
                category=Category.PERFORMANCE,
                context={"set_latency_ms": set_time, "get_latency_ms": get_time}
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_cache_latency",
            component="cache",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.PERFORMANCE
        )
        return False


async def test_cache_large_value(config: TestConfig, collector: IssueCollector) -> bool:
    """Test caching large values."""
    try:
        client = aioredis.from_url(config.redis_url)
        
        key = f"test:large:{uuid.uuid4()}"
        # 1MB value
        value = "x" * (1024 * 1024)
        
        start = time.time()
        await client.set(key, value, ex=60)
        set_time = time.time() - start
        
        start = time.time()
        result = await client.get(key)
        get_time = time.time() - start
        
        # Cleanup
        await client.delete(key)
        await client.close()
        
        if result and len(result) == len(value):
            collector.add_log(f"Large value cache test passed: 1MB, set={set_time:.2f}s, get={get_time:.2f}s")
            return True
        else:
            collector.record_issue(
                test_name="test_cache_large_value",
                component="cache",
                message=f"Large value mismatch: expected {len(value)}, got {len(result) if result else 0}",
                severity=Severity.MEDIUM,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_cache_large_value",
            component="cache",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def run_all(config: TestConfig, collector: IssueCollector) -> Tuple[int, int, int]:
    """Run all cache tests."""
    tests = [
        ("Redis Set/Get", test_redis_set_get),
        ("Redis TTL", test_redis_ttl),
        ("Redis Hash Operations", test_redis_hash_operations),
        ("Redis List Operations", test_redis_list_operations),
        ("Cache Latency", test_cache_latency),
        ("Large Value Cache", test_cache_large_value),
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
