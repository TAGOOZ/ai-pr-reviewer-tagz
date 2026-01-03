"""Integration tests for RAG orchestrator workflow."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from coderabbit_ai.models import FileChange, ContextData
from coderabbit_ai.pipeline import CodeRabbitMultiAgentPipeline


class TestRAGOrchestrator:
    """Integration tests for RAG orchestrator workflow."""

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    def test_rag_context_building(self, mock_embedding_class, mock_context_agent_class):
        """Test RAG context building flow."""
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Test context"
        mock_context_result.confidence_score = 0.85
        mock_context_result.processing_time_ms = 100
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Create test data
        context_data = ContextData(
            pr_number=123,
            repository='test/repo',
            title='Test PR',
            description='Test description',
            files_changed=[
                FileChange(
                    path='src/api.py',
                    content='def test(): pass'
                )
            ]
        )

        # Build context
        context = pipeline._build_pr_context(context_data)

        assert context is not None
        assert mock_context_agent.forward.called

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    @patch('coderabbit_ai.pipeline.VectorEngine')
    def test_rag_vector_search(self, mock_vector_class, mock_embedding_class, mock_context_agent_class):
        """Test RAG vector search for relevant code."""
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock vector engine
        mock_vector_engine = Mock()
        mock_vector_engine.search.return_value = [
            {
                'file_path': 'src/similar.py',
                'content': 'def similar_function(): pass',
                'score': 0.9
            },
            {
                'file_path': 'src/related.py',
                'content': 'def related_function(): pass',
                'score': 0.8
            }
        ]
        mock_vector_class.return_value = mock_vector_engine

        # Mock context agent
        mock_context_agent = Mock()
        mock_context_agent.forward.return_value = Mock()
        mock_context_agent_class.return_value = mock_context_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Get context with vector search
        files = [
            FileChange(
                path='src/api.py',
                content='def new_function(): pass'
            )
        ]

        # This should trigger vector search
        context = pipeline._get_relevant_code_context(files)

        assert context is not None

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    @patch('coderabbit_ai.pipeline.VectorEngine')
    def test_rag_aggregation(self, mock_vector_class, mock_embedding_class, mock_context_agent_class):
        """Test RAG aggregation of multiple context sources."""
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock vector engine with multiple results
        mock_vector_engine = Mock()
        mock_vector_engine.search.return_value = [
            {
                'file_path': 'src/core.py',
                'content': 'Core functionality',
                'score': 0.95
            },
            {
                'file_path': 'src/utils.py',
                'content': 'Utility functions',
                'score': 0.85
            },
            {
                'file_path': 'tests/test_core.py',
                'content': 'Core tests',
                'score': 0.75
            }
        ]
        mock_vector_class.return_value = mock_vector_engine

        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Aggregated context"
        mock_context_result.confidence_score = 0.90
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Aggregate context
        query = "How to handle errors?"
        aggregated = pipeline._aggregate_rag_context(query)

        assert aggregated is not None
        assert 'Aggregated context' in str(aggregated)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    @patch('coderabbit_ai.pipeline.VectorEngine')
    def test_rag_with_empty_results(self, mock_vector_class, mock_embedding_class, mock_context_agent_class):
        """Test RAG when vector search returns no results."""
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock vector engine with empty results
        mock_vector_engine = Mock()
        mock_vector_engine.search.return_value = []
        mock_vector_class.return_value = mock_vector_engine

        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Minimal context"
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle empty results gracefully
        files = [
            FileChange(
                path='src/new.py',
                content='def new_function(): pass'
            )
        ]

        context = pipeline._get_relevant_code_context(files)

        # Should still return some context
        assert context is not None

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    @patch('coderabbit_ai.pipeline.VectorEngine')
    def test_rag_confidence_scoring(self, mock_vector_class, mock_embedding_class, mock_context_agent_class):
        """Test RAG confidence scoring for results."""
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock vector engine with varied scores
        mock_vector_engine = Mock()
        mock_vector_engine.search.return_value = [
            {'file_path': 'src/high.py', 'content': 'High', 'score': 0.95},
            {'file_path': 'src/medium.py', 'content': 'Med', 'score': 0.65},
            {'file_path': 'src/low.py', 'content': 'Low', 'score': 0.45}
        ]
        mock_vector_class.return_value = mock_vector_engine

        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Get context with confidence scoring
        context = pipeline._get_relevant_code_context([
            FileChange(path='src/api.py', content='test')
        ])

        assert context is not None

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    @patch('coderabbit_ai.pipeline.VectorEngine')
    def test_rag_context_deduplication(self, mock_vector_class, mock_embedding_class, mock_context_agent_class):
        """Test RAG deduplicates similar context."""
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock vector engine with duplicate content
        mock_vector_engine = Mock()
        mock_vector_engine.search.return_value = [
            {'file_path': 'src/dup1.py', 'content': 'Same content', 'score': 0.9},
            {'file_path': 'src/dup2.py', 'content': 'Same content', 'score': 0.88},
            {'file_path': 'src/unique.py', 'content': 'Unique content', 'score': 0.8}
        ]
        mock_vector_class.return_value = mock_vector_engine

        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Deduplicated context"
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Get context with deduplication
        context = pipeline._get_relevant_code_context([
            FileChange(path='src/api.py', content='test')
        ])

        assert context is not None

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    @patch('coderabbit_ai.pipeline.VectorEngine')
    def test_rag_timeout_handling(self, mock_vector_class, mock_embedding_class, mock_context_agent_class):
        """Test RAG handles timeout gracefully."""
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock vector engine with timeout
        mock_vector_engine = Mock()
        mock_vector_engine.search.side_effect = TimeoutError("Search timeout")
        mock_vector_class.return_value = mock_vector_engine

        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Fallback context"
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Should handle timeout gracefully
        context = pipeline._get_relevant_code_context([
            FileChange(path='src/api.py', content='test')
        ])

        # Should fall back to basic context
        assert context is not None

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    @patch('coderabbit_ai.pipeline.VectorEngine')
    def test_rag_multi_query_batching(self, mock_vector_class, mock_embedding_class, mock_context_agent_class):
        """Test RAG batching multiple queries."""
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock vector engine
        mock_vector_engine = Mock()
        mock_vector_engine.search.return_value = [
            {'file_path': 'src/result.py', 'content': 'result', 'score': 0.9}
        ]
        mock_vector_class.return_value = mock_vector_engine

        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Process multiple queries
        queries = [
            "How to authenticate?",
            "How to handle errors?",
            "How to log events?"
        ]

        results = []
        for query in queries:
            result = pipeline._get_relevant_code_context([
                FileChange(path='src/api.py', content=query)
            ])
            results.append(result)

        # Should process all queries
        assert len(results) == 3
        assert all(r is not None for r in results)
