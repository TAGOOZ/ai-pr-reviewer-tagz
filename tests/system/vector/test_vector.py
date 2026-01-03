"""Tests for vector engine functionality."""

import os
import random
import time
import uuid
from typing import Tuple

import asyncpg

from ..config import TestConfig
from ..issue_collector import IssueCollector, Severity, Category


async def test_vector_table_exists(config: TestConfig, collector: IssueCollector) -> bool:
    """Test that vector_index table exists with correct schema."""
    try:
        conn = await asyncpg.connect(config.database_url, timeout=30)
        
        # Check table exists
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'vector_index'
            )
        """)
        
        if not result:
            await conn.close()
            collector.record_issue(
                test_name="test_vector_table_exists",
                component="vector",
                message="vector_index table does not exist",
                severity=Severity.HIGH,
                category=Category.DATA_INTEGRITY
            )
            return False
        
        # Check columns
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'vector_index'
        """)
        await conn.close()
        
        column_names = {row['column_name'] for row in columns}
        required = {'id', 'content_hash', 'file_path', 'repository_id', 'embedding_vector'}
        missing = required - column_names
        
        if missing:
            collector.record_issue(
                test_name="test_vector_table_exists",
                component="vector",
                message=f"Missing columns: {missing}",
                severity=Severity.HIGH,
                category=Category.DATA_INTEGRITY
            )
            return False
        
        collector.add_log(f"Vector table check passed: {len(columns)} columns")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_vector_table_exists",
            component="vector",
            error=e,
            severity=Severity.HIGH,
            category=Category.DATA_INTEGRITY
        )
        return False


async def test_vector_insertion(config: TestConfig, collector: IssueCollector) -> bool:
    """Test inserting vectors into the database."""
    try:
        conn = await asyncpg.connect(config.database_url, timeout=30)
        
        # Get a repository ID (or create test org/repo)
        repo_id = await conn.fetchval("SELECT id FROM repositories LIMIT 1")
        
        if not repo_id:
            # Create test organization and repository
            org_id = await conn.fetchval("""
                INSERT INTO organizations (name, slug) 
                VALUES ('Test Org', 'test-org-' || substr(md5(random()::text), 1, 8))
                ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
            """)
            
            repo_id = await conn.fetchval("""
                INSERT INTO repositories (organization_id, name, full_name, platform, platform_id)
                VALUES ($1, 'test-repo', 'test/test-repo', 'github', 'test-' || substr(md5(random()::text), 1, 8))
                RETURNING id
            """, org_id)
        
        # Generate test vector
        test_id = str(uuid.uuid4())
        content_hash = f"test_hash_{uuid.uuid4().hex[:16]}"
        embedding = [random.random() for _ in range(config.embedding_dimension)]
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        
        # Insert vector
        await conn.execute("""
            INSERT INTO vector_index (id, content_hash, file_path, repository_id, language, content, embedding_vector)
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
        """, uuid.UUID(test_id), content_hash, "test/file.py", repo_id, "python", "def test(): pass", embedding_str)
        
        # Verify insertion
        result = await conn.fetchval("""
            SELECT COUNT(*) FROM vector_index WHERE content_hash = $1
        """, content_hash)
        
        # Cleanup
        await conn.execute("DELETE FROM vector_index WHERE content_hash = $1", content_hash)
        await conn.close()
        
        if result == 1:
            collector.add_log("Vector insertion test passed")
            return True
        else:
            collector.record_issue(
                test_name="test_vector_insertion",
                component="vector",
                message=f"Vector not found after insertion: count={result}",
                severity=Severity.HIGH,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_vector_insertion",
            component="vector",
            error=e,
            severity=Severity.HIGH,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_vector_similarity_search(config: TestConfig, collector: IssueCollector) -> bool:
    """Test vector similarity search."""
    try:
        conn = await asyncpg.connect(config.database_url, timeout=30)
        
        # Check if pgvector extension is available
        has_vector = await conn.fetchval("""
            SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
        """)
        
        if not has_vector:
            await conn.close()
            collector.add_log("pgvector extension not available (skipped)")
            return True
        
        # Get a repository ID
        repo_id = await conn.fetchval("SELECT id FROM repositories LIMIT 1")
        if not repo_id:
            await conn.close()
            collector.add_log("No repositories found for similarity search test (skipped)")
            return True
        
        # Insert test vectors
        test_vectors = []
        for i in range(5):
            content_hash = f"sim_test_{uuid.uuid4().hex[:16]}"
            embedding = [0.1 * (i + 1)] * config.embedding_dimension
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            
            await conn.execute("""
                INSERT INTO vector_index (content_hash, file_path, repository_id, language, embedding_vector)
                VALUES ($1, $2, $3, $4, $5::vector)
            """, content_hash, f"test/file_{i}.py", repo_id, "python", embedding_str)
            test_vectors.append(content_hash)
        
        # Search for similar vectors
        query_embedding = [0.1] * config.embedding_dimension
        query_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        
        results = await conn.fetch("""
            SELECT content_hash, embedding_vector <-> $1::vector AS distance
            FROM vector_index
            WHERE content_hash = ANY($2)
            ORDER BY distance
            LIMIT 3
        """, query_str, test_vectors)
        
        # Cleanup
        await conn.execute("DELETE FROM vector_index WHERE content_hash = ANY($1)", test_vectors)
        await conn.close()
        
        if len(results) > 0:
            collector.add_log(f"Vector similarity search passed: {len(results)} results")
            return True
        else:
            collector.record_issue(
                test_name="test_vector_similarity_search",
                component="vector",
                message="No results from similarity search",
                severity=Severity.MEDIUM,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_vector_similarity_search",
            component="vector",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_batch_vector_insertion(config: TestConfig, collector: IssueCollector) -> bool:
    """Test batch vector insertion performance."""
    try:
        conn = await asyncpg.connect(config.database_url, timeout=60)
        
        repo_id = await conn.fetchval("SELECT id FROM repositories LIMIT 1")
        if not repo_id:
            await conn.close()
            collector.add_log("No repositories found for batch test (skipped)")
            return True
        
        # Prepare batch data
        batch_size = 100
        records = []
        content_hashes = []
        
        for i in range(batch_size):
            content_hash = f"batch_test_{uuid.uuid4().hex[:16]}"
            content_hashes.append(content_hash)
            embedding = [random.random() for _ in range(config.embedding_dimension)]
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            records.append((content_hash, f"test/batch_{i}.py", repo_id, "python", embedding_str))
        
        # Batch insert
        start = time.time()
        await conn.executemany("""
            INSERT INTO vector_index (content_hash, file_path, repository_id, language, embedding_vector)
            VALUES ($1, $2, $3, $4, $5::vector)
        """, records)
        elapsed = time.time() - start
        
        # Verify count
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM vector_index WHERE content_hash = ANY($1)
        """, content_hashes)
        
        # Cleanup
        await conn.execute("DELETE FROM vector_index WHERE content_hash = ANY($1)", content_hashes)
        await conn.close()
        
        if count == batch_size:
            rate = batch_size / elapsed
            collector.add_log(f"Batch insertion passed: {batch_size} vectors in {elapsed:.2f}s ({rate:.0f}/s)")
            return True
        else:
            collector.record_issue(
                test_name="test_batch_vector_insertion",
                component="vector",
                message=f"Batch insertion count mismatch: {count}/{batch_size}",
                severity=Severity.MEDIUM,
                category=Category.FUNCTIONALITY
            )
            return False
    except Exception as e:
        collector.record_failure(
            test_name="test_batch_vector_insertion",
            component="vector",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def run_all(config: TestConfig, collector: IssueCollector) -> Tuple[int, int, int]:
    """Run all vector tests."""
    tests = [
        ("Vector Table Exists", test_vector_table_exists),
        ("Vector Insertion", test_vector_insertion),
        ("Vector Similarity Search", test_vector_similarity_search),
        ("Batch Vector Insertion", test_batch_vector_insertion),
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
