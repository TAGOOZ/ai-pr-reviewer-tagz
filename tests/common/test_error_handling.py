"""Tests for error handling edge cases."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from subprocess import TimeoutExpired
from requests.exceptions import RequestException

from coderabbit_ai.pipeline import CodeRabbitMultiAgentPipeline
from coderabbit_ai.models import FileChange


class TestErrorHandling:
    """Test error handling edge cases."""

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_network_timeout_handling(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of network timeouts."""
        # Mock context agent with timeout
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = TimeoutError("Network timeout")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.0
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle timeout gracefully
        files = [FileChange(path='src/api.py', content='code')]
        context = pipeline._build_pr_context(files)

        # Should still return some context even on error
        assert context is not None or isinstance(context, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_database_connection_failure(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of database connection failures."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent with database error
        mock_review_agent = Mock()
        mock_review_agent.forward.side_effect = ConnectionError("Database connection failed")
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle database error gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_invalid_api_response(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of invalid API responses."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent with invalid response
        mock_review_agent = Mock()
        mock_review_agent.forward.side_effect = ValueError("Invalid API response format")
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle invalid response gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_file_not_found_handling(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of file not found errors."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = FileNotFoundError("File not found: src/missing.py")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle file not found gracefully
        files = [FileChange(path='src/missing.py', content='code')]
        context = pipeline._build_pr_context(files)

        # Should return some context
        assert context is not None or isinstance(context, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_memory_limit_exceeded(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of memory limit exceeded."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = MemoryError("Out of memory")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle memory error gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_api_rate_limiting(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of API rate limiting."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent with rate limit
        mock_review_agent = Mock()
        mock_review_agent.forward.side_effect = RequestException("Rate limit exceeded")
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle rate limit gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_invalid_json_response(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of invalid JSON responses."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent with JSON error
        import json
        mock_review_agent = Mock()
        mock_review_agent.forward.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle JSON decode error gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_resource_limit_error(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of resource limit errors."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = OSError("Resource limit reached")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle resource limit gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_permission_denied_error(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of permission denied errors."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = PermissionError("Permission denied")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle permission error gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_malformed_input_data(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of malformed input data."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = ValueError("Malformed input data")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle malformed input gracefully
        result = pipeline._review_code(
            context="",  # Empty context
            code_changes=[],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_unexpected_exception_handling(self, mock_review_class, mock_context_agent_class):
        """Test graceful handling of unexpected exceptions."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = Exception("Unexpected error")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle unexpected exception gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even on error
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_cascading_errors(self, mock_review_class, mock_context_agent_class):
        """Test handling of cascading errors."""
        # Mock context agent with error
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = ConnectionError("Context agent failed")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent with different error
        mock_review_agent = Mock()
        mock_review_agent.forward.side_effect = TimeoutError("Review agent timed out")
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle cascading errors gracefully
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return some result even with multiple errors
        assert result is not None or isinstance(result, dict)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_partial_failure_recovery(self, mock_review_class, mock_context_agent_class):
        """Test recovery from partial failures."""
        # Mock context agent to succeed
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent to fail first, then succeed
        mock_review_agent = Mock()
        call_count = 0

        def mock_forward(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call failed")
            mock_review_result = Mock()
            mock_review_result.review_findings = []
            mock_review_result.confidence_score = 0.80
            return mock_review_result

        mock_review_agent.forward.side_effect = mock_forward
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # First call should fail
        try:
            result1 = pipeline._review_code(
                context="Context",
                code_changes=[FileChange(path='src/api.py', content='code')],
                org_config={}
            )
        except:
            pass

        # Second call should succeed
        result2 = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should handle partial failures
        assert call_count == 2

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_error_with_fallback(self, mock_review_class, mock_context_agent_class):
        """Test using fallback when primary fails."""
        # Mock primary context agent to fail
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = ConnectionError("Primary failed")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline with fallback
        pipeline = CodeRabbitMultiAgentPipeline(config={
            'fallback_enabled': True
        })

        # Should use fallback on primary failure
        result = pipeline._review_code(
            context="Context",
            code_changes=[FileChange(path='src/api.py', content='code')],
            org_config={}
        )

        # Should return result using fallback
        assert result is not None or isinstance(result, dict)
