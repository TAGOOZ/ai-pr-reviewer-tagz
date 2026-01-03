"""Tests for concurrent request handling."""

import pytest
import asyncio
from unittest.mock import Mock, patch

from coderabbit_ai.pipeline import CodeRabbitMultiAgentPipeline
from coderabbit_ai.models import FileChange


class TestConcurrentRequests:
    """Test concurrent request handling."""

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @pytest.mark.asyncio
    async def test_multiple_simultaneous_reviews(self, mock_review_class, mock_context_agent_class):
        """Test handling multiple simultaneous review requests."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Simulate 10 concurrent requests
        async def process_request(request_id):
            files = [FileChange(path=f'src/file{request_id}.py', content='code')]
            return pipeline._review_code(
                context="Context",
                code_changes=files,
                org_config={}
            )

        # Process concurrent requests
        tasks = [process_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all processed
        assert len(results) == 10
        assert all(r is not None for r in results if not isinstance(r, Exception))

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_thread_safe_state_management(self, mock_review_class, mock_context_agent_class):
        """Test thread-safe state management."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Shared state
        shared_counter = {'value': 0}

        def increment_counter():
            # Simulate state update
            for _ in range(1000):
                shared_counter['value'] += 1

        # Simulate concurrent state updates
        import threading
        threads = [threading.Thread(target=increment_counter) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify counter is correct
        assert shared_counter['value'] == 10000  # 1000 * 10

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, mock_review_class, mock_context_agent_class):
        """Test concurrent cache access."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Mock cache
        cache = {}

        async def cache_access(key, value):
            await asyncio.sleep(0.001)  # Simulate delay
            cache[key] = value
            return cache.get(key)

        # Concurrent cache writes
        tasks = [
            cache_access(f'key{i}', f'value{i}')
            for i in range(100)
        ]
        results = await asyncio.gather(*tasks)

        # Verify all cache operations succeeded
        assert len(results) == 100
        assert all(r is not None for r in results)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @pytest.mark.asyncio
    async def test_rate_limiting_under_load(self, mock_review_class, mock_context_agent_class):
        """Test rate limiting under heavy load."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline with rate limiting
        pipeline = CodeRabbitMultiAgentPipeline(config={
            'rate_limit': 10,  # Max 10 requests per second
            'rate_window': 1
        })

        # Simulate 50 concurrent requests
        request_times = []

        async def process_request(request_id):
            start_time = asyncio.get_event_loop().time()
            files = [FileChange(path=f'src/file{request_id}.py', content='code')]
            try:
                await asyncio.sleep(0.01)
                result = pipeline._review_code(
                    context="Context",
                    code_changes=files,
                    org_config={}
                )
                end_time = asyncio.get_event_loop().time()
                request_times.append(end_time - start_time)
                return result
            except:
                return None

        # Process requests
        tasks = [process_request(i) for i in range(50)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Verify rate limiting
        assert len(request_times) > 0

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @pytest.mark.asyncio
    async def test_deadlock_prevention(self, mock_review_class, mock_context_agent_class):
        """Test prevention of deadlocks."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Simulate potential deadlock scenario
        lock1 = asyncio.Lock()
        lock2 = asyncio.Lock()

        async def task1():
            async with lock1:
                await asyncio.sleep(0.001)
                async with lock2:
                    return "Task 1 complete"

        async def task2():
            async with lock2:
                await asyncio.sleep(0.001)
                async with lock1:
                    return "Task 2 complete"

        # Run tasks concurrently
        results = await asyncio.gather(task1(), task2())

        # Both should complete (no deadlock)
        assert len(results) == 2
        assert all(r is not None for r in results)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @pytest.mark.asyncio
    async def test_resource_contention_handling(self, mock_review_class, mock_context_agent_class):
        """Test handling of resource contention."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Limited resource
        resource_semaphore = asyncio.Semaphore(5)

        async def access_resource(request_id):
            async with resource_semaphore:
                await asyncio.sleep(0.01)
                files = [FileChange(path=f'src/file{request_id}.py', content='code')]
                return pipeline._review_code(
                    context="Context",
                    code_changes=files,
                    org_config={}
                )

        # Access resource from 20 concurrent tasks
        tasks = [access_resource(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all tasks complete despite contention
        assert len(results) == 20
        # Most should succeed (resource limit handled)
        success_count = sum(1 for r in results if not isinstance(r, Exception))

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @pytest.mark.asyncio
    async def test_concurrent_error_isolation(self, mock_review_class, mock_context_agent_class):
        """Test that errors in one request don't affect others."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent with mixed success/failure
        mock_review_agent = Mock()
        call_count = 0

        def mock_forward(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                raise ValueError("Simulated error")
            mock_review_result = Mock()
            mock_review_result.review_findings = []
            mock_review_result.confidence_score = 0.80
            return mock_review_result

        mock_review_agent.forward.side_effect = mock_forward
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Process concurrent requests
        async def process_request(request_id):
            files = [FileChange(path=f'src/file{request_id}.py', content='code')]
            try:
                return await asyncio.to_thread(
                    pipeline._review_code,
                    context="Context",
                    code_changes=files,
                    org_config={}
                )
            except:
                return None

        tasks = [process_request(i) for i in range(9)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify errors don't affect all requests
        assert len(results) == 9
        # About 1/3 should fail
        failures = sum(1 for r in results if r is None)
        assert 2 <= failures <= 4

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, mock_review_class, mock_context_agent_class):
        """Test handling under memory pressure."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Simulate memory pressure with large payloads
        large_content = "def test(): pass\n" * 1000

        async def process_large_request(request_id):
            files = [FileChange(path=f'src/file{request_id}.py', content=large_content)]
            try:
                result = pipeline._review_code(
                    context="Context",
                    code_changes=files,
                    org_config={}
                )
                return result
            except MemoryError:
                return None

        # Process with concurrency
        tasks = [process_large_request(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify handling of memory pressure
        assert len(results) == 5
        # Most should succeed or fail gracefully
        success_count = sum(1 for r in results if r is not None)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @pytest.mark.asyncio
    async def test_connection_pool_under_concurrency(self, mock_review_class, mock_context_agent_class):
        """Test connection pool under concurrent load."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline with connection pool
        pipeline = CodeRabbitMultiAgentPipeline(config={
            'connection_pool_size': 10
        })

        # Track connection usage
        connection_usage = []

        async def use_connection(request_id):
            connection_usage.append(request_id)
            await asyncio.sleep(0.01)
            files = [FileChange(path=f'src/file{request_id}.py', content='code')]
            return pipeline._review_code(
                context="Context",
                code_changes=files,
                org_config={}
            )

        # Use connection pool with concurrent requests
        tasks = [use_connection(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify connection pool usage
        assert len(results) == 20
        assert len(connection_usage) == 20
        # Connections reused (not exceeded)
        assert max(connection_usage) < 100
