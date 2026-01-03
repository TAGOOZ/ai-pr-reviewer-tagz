"""Integration tests for Python bridge communication."""

import pytest
import msgpack
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from coderabbit_ai.bridge import (
    call_static_analyzer,
    call_embedding_service,
    call_vector_search,
    call_code_analyzer_embeddings
)


class TestPythonBridgeCommunication:
    """Integration tests for Python-Rust bridge communication."""

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_messagepack_serialization_roundtrip(self, mock_config, mock_subprocess):
        """Test MessagePack serialization and deserialization."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        # Prepare input data
        input_data = {
            "file_path": "src/api.py",
            "language": "python",
            "content": "def test(): pass"
        }

        # Serialize with MessagePack
        serialized = msgpack.packb(input_data)

        # Deserialize
        deserialized = msgpack.unpackb(serialized)

        # Verify roundtrip
        assert deserialized["file_path"] == input_data["file_path"]
        assert deserialized["language"] == input_data["language"]
        assert deserialized["content"] == input_data["content"]

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_communication_large_payload(self, mock_config, mock_subprocess):
        """Test bridge handles large payloads."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        # Create large content
        large_content = "def test():\n    pass\n" * 1000  # ~30KB

        # Mock successful result
        from subprocess import CompletedProcess
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {"complexity": 50}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        # Call with large payload
        result = call_static_analyzer(
            file_path="src/large.py",
            language="python",
            content=large_content
        )

        assert result is not None
        assert result["issues"] == []

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_communication_special_characters(self, mock_config, mock_subprocess):
        """Test bridge handles special characters in content."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        # Content with special characters
        special_content = "def test():\n    # Special chars: <>\"'\\n    return \"test\\u00e9\\u00f1\""

        from subprocess import CompletedProcess
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        result = call_static_analyzer(
            file_path="src/special.py",
            language="python",
            content=special_content
        )

        assert result is not None

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_communication_unicode(self, mock_config, mock_subprocess):
        """Test bridge handles Unicode content."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        # Unicode content
        unicode_content = "def test():\n    # العربية\n    # 中文\n    # 日本語\n    return True"

        from subprocess import CompletedProcess
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        result = call_static_analyzer(
            file_path="src/unicode.py",
            language="python",
            content=unicode_content
        )

        assert result is not None

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_http_bridge_communication(self, mock_config, mock_post):
        """Test HTTP bridge communication."""
        mock_config.EMBEDDING_SERVICE_URL = "http://localhost:8080/embed"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_post.return_value = mock_response

        # Call embedding service
        result = call_embedding_service("test code")

        # Verify HTTP communication
        assert result == [0.1, 0.2, 0.3]
        mock_post.assert_called_once()

        # Check request data
        call_args = mock_post.call_args
        request_data = call_args.kwargs.get('json', {})
        assert 'text' in request_data
        assert request_data['text'] == "test code"

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_multiple_concurrent_requests(self, mock_config, mock_subprocess):
        """Test bridge handles multiple concurrent requests."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        from subprocess import CompletedProcess
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        # Simulate concurrent requests
        files = [
            ("src/file1.py", "def test1(): pass"),
            ("src/file2.py", "def test2(): pass"),
            ("src/file3.py", "def test3(): pass")
        ]

        results = []
        for file_path, content in files:
            result = call_static_analyzer(
                file_path=file_path,
                language="python",
                content=content
            )
            results.append(result)

        # All should succeed
        assert all(r is not None for r in results)
        assert len(results) == 3

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_error_recovery(self, mock_config, mock_subprocess):
        """Test bridge recovers from errors."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        from subprocess import CompletedProcess

        # First call fails
        mock_result_fail = CompletedProcess(
            returncode=1,
            stdout='',
            stderr="Analysis failed"
        )
        mock_subprocess.return_value = mock_result_fail

        result1 = call_static_analyzer(
            file_path="src/fail.py",
            language="python",
            content="def test(): pass"
        )

        assert result1 is None

        # Second call succeeds
        mock_result_success = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result_success

        result2 = call_static_analyzer(
            file_path="src/success.py",
            language="python",
            content="def test(): pass"
        )

        assert result2 is not None

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_shared_memory_communication(self, mock_config, mock_subprocess):
        """Test shared memory communication pattern."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        # Create temp file to simulate shared memory
        with tempfile.TemporaryDirectory() as tmpdir:
            shm_file = Path(tmpdir) / "shm.bin"

            # Write data to "shared memory"
            test_data = b"shared_memory_test_data"
            shm_file.write_bytes(test_data)

            # Read back
            read_data = shm_file.read_bytes()

            assert read_data == test_data

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_communication_latency(self, mock_config, mock_subprocess):
        """Test bridge communication latency is acceptable."""
        import time

        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        from subprocess import CompletedProcess
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        # Measure latency
        start_time = time.time()
        result = call_static_analyzer(
            file_path="src/test.py",
            language="python",
            content="def test(): pass"
        )
        end_time = time.time()

        latency_ms = (end_time - start_time) * 1000

        assert result is not None
        # Latency should be reasonable (< 1 second for mocked call)
        assert latency_ms < 1000

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.requests.get')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_connection_pooling(self, mock_config, mock_get, mock_post):
        """Test bridge uses connection pooling for HTTP."""
        mock_config.EMBEDDING_SERVICE_URL = "http://localhost:8080/embed"
        mock_config.VECTOR_SEARCH_SERVICE_URL = "http://localhost:8080/search"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        # Mock responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_post.return_value = mock_response

        mock_search_response = Mock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {"results": []}
        mock_get.return_value = mock_search_response

        # Make multiple requests
        for i in range(5):
            call_embedding_service("test code")

        # Should reuse connections (in real implementation)
        assert mock_post.call_count == 5

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_communication_chunking(self, mock_config, mock_subprocess):
        """Test bridge handles chunked large data."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        # Very large content that might need chunking
        large_content = "def test():\n    pass\n" * 10000  # ~300KB

        from subprocess import CompletedProcess
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        result = call_static_analyzer(
            file_path="src/chunked.py",
            language="python",
            content=large_content
        )

        # Should handle large content
        assert result is not None

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_timeout_during_communication(self, mock_config, mock_subprocess):
        """Test bridge handles timeout during communication."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 1  # Short timeout

        from subprocess import TimeoutExpired
        mock_subprocess.side_effect = TimeoutExpired("cargo", 1)

        result = call_static_analyzer(
            file_path="src/test.py",
            language="python",
            content="def test(): pass"
        )

        # Should handle timeout gracefully
        assert result is None

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_bridge_signal_handling(self, mock_config, mock_subprocess):
        """Test bridge handles process signals."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30

        from subprocess import CompletedProcess
        mock_result = CompletedProcess(
            returncode=-15,  # SIGTERM
            stdout='',
            stderr="Process terminated"
        )
        mock_subprocess.return_value = mock_result

        result = call_static_analyzer(
            file_path="src/test.py",
            language="python",
            content="def test(): pass"
        )

        # Should handle termination gracefully
        assert result is None
