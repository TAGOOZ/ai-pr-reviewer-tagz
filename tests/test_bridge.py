"""Unit tests for bridge.py."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from subprocess import TimeoutExpired, CompletedProcess
from requests.exceptions import RequestException

from coderabbit_ai.bridge import (
    call_static_analyzer,
    call_embedding_service,
    call_vector_search,
    call_code_analyzer_embeddings
)


class TestCallStaticAnalyzer:
    """Test call_static_analyzer function."""

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_static_analyzer_success(self, mock_config, mock_subprocess):
        """Test successful static analyzer call."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {"complexity": 5}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        result = call_static_analyzer(
            file_path="src/api.py",
            language="python",
            content="def test(): pass"
        )

        assert result is not None
        assert "issues" in result
        assert "metrics" in result
        mock_subprocess.assert_called_once()

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_static_analyzer_returncode_error(self, mock_config, mock_subprocess):
        """Test static analyzer with non-zero returncode."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30
        mock_result = CompletedProcess(
            returncode=1,
            stdout='',
            stderr="Analysis failed"
        )
        mock_subprocess.return_value = mock_result

        result = call_static_analyzer(
            file_path="src/api.py",
            language="python",
            content="def test(): pass"
        )

        assert result is None

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_static_analyzer_timeout(self, mock_config, mock_subprocess):
        """Test static analyzer with timeout."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30
        mock_subprocess.side_effect = TimeoutExpired("cargo", 30)

        result = call_static_analyzer(
            file_path="src/api.py",
            language="python",
            content="def test(): pass"
        )

        assert result is None

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_static_analyzer_json_error(self, mock_config, mock_subprocess):
        """Test static analyzer with invalid JSON output."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30
        mock_result = CompletedProcess(
            returncode=0,
            stdout='invalid json',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        result = call_static_analyzer(
            file_path="src/api.py",
            language="python",
            content="def test(): pass"
        )

        assert result is None

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_static_analyzer_exception(self, mock_config, mock_subprocess):
        """Test static analyzer with generic exception."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30
        mock_subprocess.side_effect = Exception("Unknown error")

        result = call_static_analyzer(
            file_path="src/api.py",
            language="python",
            content="def test(): pass"
        )

        assert result is None

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_static_analyzer_input_format(self, mock_config, mock_subprocess):
        """Test that input is properly formatted as JSON."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": []}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        call_static_analyzer(
            file_path="src/api.py",
            language="python",
            content="def test(): pass"
        )

        # Verify input was JSON
        call_args = mock_subprocess.call_args
        input_data = call_args.kwargs.get('input', call_args.args[0] if call_args.args else None)

        # Verify input can be parsed as JSON
        parsed = json.loads(input_data)
        assert parsed["file_path"] == "src/api.py"
        assert parsed["language"] == "python"
        assert parsed["content"] == "def test(): pass"


class TestCallEmbeddingService:
    """Test call_embedding_service function."""

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_embedding_service_success(self, mock_config, mock_post):
        """Test successful embedding service call."""
        mock_config.EMBEDDING_SERVICE_URL = "http://localhost:8080/embed"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_post.return_value = mock_response

        result = call_embedding_service("test code")

        assert result == [0.1, 0.2, 0.3]
        mock_post.assert_called_once()

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_embedding_service_status_error(self, mock_config, mock_post):
        """Test embedding service with error status."""
        mock_config.EMBEDDING_SERVICE_URL = "http://localhost:8080/embed"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = call_embedding_service("test code")

        assert result is None

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_embedding_service_request_exception(self, mock_config, mock_post):
        """Test embedding service with request exception."""
        mock_config.EMBEDDING_SERVICE_URL = "http://localhost:8080/embed"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_post.side_effect = RequestException("Connection error")

        result = call_embedding_service("test code")

        assert result is None

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_embedding_service_generic_exception(self, mock_config, mock_post):
        """Test embedding service with generic exception."""
        mock_config.EMBEDDING_SERVICE_URL = "http://localhost:8080/embed"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_post.side_effect = Exception("Unknown error")

        result = call_embedding_service("test code")

        assert result is None


class TestCallVectorSearch:
    """Test call_vector_search function."""

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_vector_search_success(self, mock_config, mock_post):
        """Test successful vector search."""
        mock_config.VECTOR_SEARCH_SERVICE_URL = "http://localhost:8080/search"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200
        mock_config.DEFAULT_TOP_K_RESULTS = 5

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"code": "test code 1", "score": 0.9},
                {"code": "test code 2", "score": 0.8}
            ]
        }
        mock_post.return_value = mock_response

        query_embedding = [0.1, 0.2, 0.3]
        result = call_vector_search(query_embedding, top_k=3)

        assert result is not None
        assert len(result) == 2
        assert result[0]["score"] == 0.9

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_vector_search_default_top_k(self, mock_config, mock_post):
        """Test vector search with default top_k."""
        mock_config.VECTOR_SEARCH_SERVICE_URL = "http://localhost:8080/search"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200
        mock_config.DEFAULT_TOP_K_RESULTS = 10

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_post.return_value = mock_response

        query_embedding = [0.1, 0.2, 0.3]
        result = call_vector_search(query_embedding)

        # Verify default top_k was used
        call_args = mock_post.call_args
        request_data = call_args.kwargs.get('json', call_args.args[0] if call_args.args else None)
        assert request_data["top_k"] == 10

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_vector_search_status_error(self, mock_config, mock_post):
        """Test vector search with error status."""
        mock_config.VECTOR_SEARCH_SERVICE_URL = "http://localhost:8080/search"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_response = Mock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response

        query_embedding = [0.1, 0.2, 0.3]
        result = call_vector_search(query_embedding)

        assert result is None

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_vector_search_request_exception(self, mock_config, mock_post):
        """Test vector search with request exception."""
        mock_config.VECTOR_SEARCH_SERVICE_URL = "http://localhost:8080/search"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_post.side_effect = RequestException("Connection error")

        query_embedding = [0.1, 0.2, 0.3]
        result = call_vector_search(query_embedding)

        assert result is None

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_vector_search_empty_results(self, mock_config, mock_post):
        """Test vector search with no results."""
        mock_config.VECTOR_SEARCH_SERVICE_URL = "http://localhost:8080/search"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_post.return_value = mock_response

        query_embedding = [0.1, 0.2, 0.3]
        result = call_vector_search(query_embedding)

        assert result == []


class TestCallCodeAnalyzerEmbeddings:
    """Test call_code_analyzer_embeddings function."""

    @patch('coderabbit_ai.bridge.call_embedding_service')
    def test_code_analyzer_embeddings_service_success(self, mock_call_embedding):
        """Test using embedding service successfully."""
        mock_call_embedding.return_value = [0.1, 0.2, 0.3, 0.4]

        result = call_code_analyzer_embeddings("def test(): pass")

        assert result == [0.1, 0.2, 0.3, 0.4]
        mock_call_embedding.assert_called_once_with("def test(): pass")

    @patch('coderabbit_ai.bridge.call_embedding_service')
    @patch('coderabbit_ai.bridge.EmbeddingService')
    def test_code_analyzer_embeddings_fallback(self, mock_embedding_service, mock_call_embedding):
        """Test fallback to local embedding service."""
        # External service fails
        mock_call_embedding.return_value = None

        # Local service succeeds
        mock_service = Mock()
        mock_service.generate_embedding.return_value = [0.5, 0.6, 0.7]
        mock_embedding_service.return_value = mock_service

        result = call_code_analyzer_embeddings("def test(): pass")

        assert result == [0.5, 0.6, 0.7]
        mock_service.generate_embedding.assert_called_once_with("def test(): pass")

    @patch('coderabbit_ai.bridge.call_embedding_service')
    @patch('coderabbit_ai.bridge.EmbeddingService')
    def test_code_analyzer_embeddings_fallback_fails(self, mock_embedding_service, mock_call_embedding):
        """Test when both services fail."""
        # External service fails
        mock_call_embedding.return_value = None

        # Local service fails
        mock_service = Mock()
        mock_service.generate_embedding.side_effect = Exception("Service error")
        mock_embedding_service.return_value = mock_service

        result = call_code_analyzer_embeddings("def test(): pass")

        assert result is None

    @patch('coderabbit_ai.bridge.call_embedding_service')
    @patch('coderabbit_ai.bridge.EmbeddingService')
    def test_code_analyzer_embeddings_import_error(self, mock_embedding_service, mock_call_embedding):
        """Test when EmbeddingService import fails."""
        # External service fails
        mock_call_embedding.return_value = None

        # Import fails
        mock_embedding_service.side_effect = ImportError("Module not found")

        result = call_code_analyzer_embeddings("def test(): pass")

        assert result is None

    @patch('coderabbit_ai.bridge.call_embedding_service')
    @patch('coderabbit_ai.bridge.EmbeddingService')
    def test_code_analyzer_embeddings_generic_exception(self, mock_embedding_service, mock_call_embedding):
        """Test with generic exception during embedding generation."""
        # External service fails
        mock_call_embedding.return_value = None

        # Local service raises generic exception
        mock_service = Mock()
        mock_service.generate_embedding.side_effect = ValueError("Invalid input")
        mock_embedding_service.return_value = mock_service

        result = call_code_analyzer_embeddings("invalid code")

        assert result is None


class TestInputValidation:
    """Test input validation for bridge functions."""

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_static_analyzer_empty_content(self, mock_config, mock_subprocess):
        """Test static analyzer with empty content."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": []}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        result = call_static_analyzer(
            file_path="src/empty.py",
            language="python",
            content=""
        )

        assert result is not None
        assert result["issues"] == []

    @patch('coderabbit_ai.bridge.subprocess.run')
    @patch('coderabbit_ai.bridge.config')
    def test_static_analyzer_special_characters(self, mock_config, mock_subprocess):
        """Test static analyzer with special characters in content."""
        mock_config.STATIC_ANALYZER_TIMEOUT = 30
        mock_result = CompletedProcess(
            returncode=0,
            stdout='{"issues": [], "metrics": {}}',
            stderr=""
        )
        mock_subprocess.return_value = mock_result

        special_content = "def test(): # Special chars: <>\"'\\"
        result = call_static_analyzer(
            file_path="src/special.py",
            language="python",
            content=special_content
        )

        assert result is not None

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_embedding_empty_text(self, mock_config, mock_post):
        """Test embedding service with empty text."""
        mock_config.EMBEDDING_SERVICE_URL = "http://localhost:8080/embed"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.0, 0.0, 0.0]}
        mock_post.return_value = mock_response

        result = call_embedding_service("")

        assert result == [0.0, 0.0, 0.0]

    @patch('coderabbit_ai.bridge.requests.post')
    @patch('coderabbit_ai.bridge.config')
    def test_vector_search_empty_embedding(self, mock_config, mock_post):
        """Test vector search with empty embedding."""
        mock_config.VECTOR_SEARCH_SERVICE_URL = "http://localhost:8080/search"
        mock_config.HTTP_REQUEST_TIMEOUT = 10
        mock_config.HTTP_STATUS_OK = 200

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_post.return_value = mock_response

        result = call_vector_search([])

        assert result == []
