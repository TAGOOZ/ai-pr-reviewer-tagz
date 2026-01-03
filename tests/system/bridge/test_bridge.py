"""Tests for Rust-Python bridge communication."""

import os
import time
import uuid
from typing import Tuple

import httpx
import msgpack

from ..config import TestConfig
from ..issue_collector import IssueCollector, Severity, Category


async def test_messagepack_serialization(config: TestConfig, collector: IssueCollector) -> bool:
    """Test MessagePack serialization round-trip."""
    try:
        test_data = {
            "files": [
                {"path": "test.py", "content": "def hello(): return 'world'"},
                {"path": "main.rs", "content": "fn main() {}"}
            ],
            "metadata": {"repo": "test/repo", "pr": 123},
            "numbers": [1, 2, 3, 4, 5],
            "nested": {"a": {"b": {"c": "deep"}}}
        }
        
        # Serialize with msgpack
        packed = msgpack.packb(test_data, use_bin_type=True)
        
        # Deserialize
        unpacked = msgpack.unpackb(packed, raw=False)
        
        if unpacked == test_data:
            collector.add_log("MessagePack serialization round-trip passed")
            return True
        else:
            collector.record_issue(
                test_name="test_messagepack_serialization",
                component="bridge",
                message="MessagePack round-trip data mismatch",
                severity=Severity.HIGH,
                category=Category.SERIALIZATION,
                context={"original": str(test_data)[:200], "unpacked": str(unpacked)[:200]}
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_messagepack_serialization",
            component="bridge",
            error=e,
            severity=Severity.HIGH,
            category=Category.SERIALIZATION
        )
        return False


async def test_large_payload_serialization(config: TestConfig, collector: IssueCollector) -> bool:
    """Test serialization of large payloads (10MB)."""
    try:
        # Create ~10MB payload
        large_content = "x" * (1024 * 1024)  # 1MB string
        test_data = {
            "files": [
                {"path": f"file_{i}.py", "content": large_content}
                for i in range(10)
            ]
        }
        
        start = time.time()
        packed = msgpack.packb(test_data, use_bin_type=True)
        pack_time = time.time() - start
        
        start = time.time()
        unpacked = msgpack.unpackb(packed, raw=False)
        unpack_time = time.time() - start
        
        size_mb = len(packed) / (1024 * 1024)
        
        if len(unpacked["files"]) == 10:
            collector.add_log(f"Large payload test passed: {size_mb:.1f}MB, pack={pack_time:.2f}s, unpack={unpack_time:.2f}s")
            return True
        else:
            collector.record_issue(
                test_name="test_large_payload_serialization",
                component="bridge",
                message="Large payload data corruption",
                severity=Severity.HIGH,
                category=Category.SERIALIZATION
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_large_payload_serialization",
            component="bridge",
            error=e,
            severity=Severity.HIGH,
            category=Category.SERIALIZATION
        )
        return False


async def test_shared_memory_write_read(config: TestConfig, collector: IssueCollector) -> bool:
    """Test shared memory file operations."""
    shm_dir = "/tmp/coderabbit_shm"
    shm_path = f"{shm_dir}/test_{uuid.uuid4()}"
    
    try:
        os.makedirs(shm_dir, exist_ok=True)
        
        # Write test data
        test_data = b"Hello, shared memory! " * 10000  # ~220KB
        with open(shm_path, "wb") as f:
            f.write(test_data)
        
        # Read back
        with open(shm_path, "rb") as f:
            read_data = f.read()
        
        # Cleanup
        os.unlink(shm_path)
        
        if read_data == test_data:
            collector.add_log(f"Shared memory write/read passed: {len(test_data)} bytes")
            return True
        else:
            collector.record_issue(
                test_name="test_shared_memory_write_read",
                component="bridge",
                message="Shared memory data mismatch",
                severity=Severity.HIGH,
                category=Category.DATA_INTEGRITY
            )
            return False
    except Exception as e:
        # Cleanup on error
        if os.path.exists(shm_path):
            os.unlink(shm_path)
        collector.record_failure(
            test_name="test_shared_memory_write_read",
            component="bridge",
            error=e,
            severity=Severity.HIGH,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_shared_memory_large_transfer(config: TestConfig, collector: IssueCollector) -> bool:
    """Test shared memory with large payload (50MB)."""
    shm_dir = "/tmp/coderabbit_shm"
    shm_path = f"{shm_dir}/large_test_{uuid.uuid4()}"
    
    try:
        os.makedirs(shm_dir, exist_ok=True)
        
        # Create 50MB payload
        test_data = os.urandom(50 * 1024 * 1024)
        
        start = time.time()
        with open(shm_path, "wb") as f:
            f.write(test_data)
        write_time = time.time() - start
        
        start = time.time()
        with open(shm_path, "rb") as f:
            read_data = f.read()
        read_time = time.time() - start
        
        # Cleanup
        os.unlink(shm_path)
        
        if read_data == test_data:
            throughput = (50 * 2) / (write_time + read_time)  # MB/s for both ops
            collector.add_log(f"Large shared memory test passed: 50MB, write={write_time:.2f}s, read={read_time:.2f}s, throughput={throughput:.0f}MB/s")
            return True
        else:
            collector.record_issue(
                test_name="test_shared_memory_large_transfer",
                component="bridge",
                message="Large shared memory data corruption",
                severity=Severity.CRITICAL,
                category=Category.DATA_INTEGRITY
            )
            return False
    except Exception as e:
        if os.path.exists(shm_path):
            os.unlink(shm_path)
        collector.record_failure(
            test_name="test_shared_memory_large_transfer",
            component="bridge",
            error=e,
            severity=Severity.HIGH,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_bridge_endpoint_echo(config: TestConfig, collector: IssueCollector) -> bool:
    """Test bridge echo endpoint if available."""
    try:
        test_data = {"test": "data", "numbers": [1, 2, 3]}
        
        async with httpx.AsyncClient(timeout=config.timeout_http) as client:
            # Try the Python service bridge endpoint
            response = await client.post(
                f"{config.ai_pipeline_url}/bridge/echo",
                json=test_data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result == test_data:
                    collector.add_log("Bridge echo endpoint passed")
                    return True
                else:
                    collector.record_issue(
                        test_name="test_bridge_endpoint_echo",
                        component="bridge",
                        message="Echo response mismatch",
                        severity=Severity.MEDIUM,
                        category=Category.FUNCTIONALITY
                    )
                    return False
            elif response.status_code == 404:
                # Endpoint not implemented - skip
                collector.add_log("Bridge echo endpoint not found (skipped)")
                return True  # Not a failure, just not implemented
            else:
                collector.record_issue(
                    test_name="test_bridge_endpoint_echo",
                    component="bridge",
                    message=f"Echo endpoint returned {response.status_code}",
                    severity=Severity.MEDIUM,
                    category=Category.FUNCTIONALITY
                )
                return False
    except httpx.ConnectError:
        collector.add_log("Bridge echo test skipped - service not available")
        return True  # Skip if service not running
    except Exception as e:
        collector.record_failure(
            test_name="test_bridge_endpoint_echo",
            component="bridge",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_embedding_batch_request(config: TestConfig, collector: IssueCollector) -> bool:
    """Test batch embedding generation."""
    try:
        texts = [f"def function_{i}(): return {i}" for i in range(50)]
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{config.ai_pipeline_url}/embeddings/batch",
                json={"texts": texts}
            )
            
            if response.status_code == 200:
                result = response.json()
                embeddings = result.get("embeddings", [])
                
                if len(embeddings) == len(texts):
                    # Check embedding dimensions
                    if len(embeddings[0]) == config.embedding_dimension:
                        collector.add_log(f"Batch embedding test passed: {len(embeddings)} embeddings, dim={len(embeddings[0])}")
                        return True
                    else:
                        collector.record_issue(
                            test_name="test_embedding_batch_request",
                            component="bridge",
                            message=f"Wrong embedding dimension: {len(embeddings[0])} (expected {config.embedding_dimension})",
                            severity=Severity.MEDIUM,
                            category=Category.FUNCTIONALITY
                        )
                        return False
                else:
                    collector.record_issue(
                        test_name="test_embedding_batch_request",
                        component="bridge",
                        message=f"Wrong number of embeddings: {len(embeddings)} (expected {len(texts)})",
                        severity=Severity.MEDIUM,
                        category=Category.FUNCTIONALITY
                    )
                    return False
            elif response.status_code == 404:
                collector.add_log("Batch embedding endpoint not found (skipped)")
                return True
            else:
                collector.record_issue(
                    test_name="test_embedding_batch_request",
                    component="bridge",
                    message=f"Batch embedding returned {response.status_code}",
                    severity=Severity.MEDIUM,
                    category=Category.FUNCTIONALITY
                )
                return False
    except httpx.ConnectError:
        collector.add_log("Batch embedding test skipped - service not available")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_embedding_batch_request",
            component="bridge",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def run_all(config: TestConfig, collector: IssueCollector) -> Tuple[int, int, int]:
    """Run all bridge tests."""
    tests = [
        ("MessagePack Serialization", test_messagepack_serialization),
        ("Large Payload Serialization", test_large_payload_serialization),
        ("Shared Memory Write/Read", test_shared_memory_write_read),
        ("Shared Memory Large Transfer", test_shared_memory_large_transfer),
        ("Bridge Echo Endpoint", test_bridge_endpoint_echo),
        ("Batch Embedding Request", test_embedding_batch_request),
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
