"""Unit tests for EmbeddingService."""

import os
import pytest
import numpy as np
from unittest.mock import Mock, patch
from coderabbit_ai.embeddings import EmbeddingService


@pytest.fixture
def embedding_service():
    """Create an EmbeddingService instance for testing."""
    service = EmbeddingService(model_name="all-MiniLM-L6-v2", device="cpu")
    return service


class TestEmbeddingServiceInitialization:
    """Test suite for EmbeddingService initialization."""

    def test_default_initialization(self):
        """Test that EmbeddingService initializes with default model."""
        service = EmbeddingService()
        assert service.model_name == "all-MiniLM-L6-v2"
        assert service.model is not None
        assert service.dimension == 384

    def test_custom_model_initialization(self):
        """Test initialization with custom model."""
        service = EmbeddingService(model_name="all-mpnet-base-v2", device="cpu")
        assert service.model_name == "all-mpnet-base-v2"
        assert service.dimension == 768

    def test_cuda_device_selection(self):
        """Test CUDA device selection when available."""
        with patch('coderabbit_ai.embeddings.torch.cuda.is_available', return_value=True):
            service = EmbeddingService(model_name="all-MiniLM-L6-v2", device=None)
            assert service.device == "cuda"

    def test_cpu_device_selection(self):
        """Test CPU device selection when CUDA unavailable."""
        with patch('coderabbit_ai.embeddings.torch.cuda.is_available', return_value=False):
            service = EmbeddingService(model_name="all-MiniLM-L6-v2", device=None)
            assert service.device == "cpu"

    def test_unknown_model_fallback(self):
        """Test fallback to default model for unknown model."""
        service = EmbeddingService(model_name="unknown-model", device="cpu")
        assert service.model_name == "all-MiniLM-L6-v2"


class TestEmbeddingGeneration:
    """Test suite for embedding generation."""

    def test_empty_text_list(self, embedding_service):
        """Test handling of empty text list."""
        result = embedding_service.generate_embeddings([])
        assert isinstance(result, np.ndarray)
        assert result.shape == (0,)

    def test_single_text_embedding(self, embedding_service):
        """Test generation of single embedding."""
        texts = ["Hello, world!"]
        result = embedding_service.generate_embeddings(texts, batch_size=1)
        assert isinstance(result, np.ndarray)
        assert result.shape[0] == 1
        assert result.shape[1] == 384

    def test_batch_embeddings(self, embedding_service):
        """Test batch embedding generation."""
        texts = ["First text", "Second text", "Third text"]
        result = embedding_service.generate_embeddings(texts, batch_size=3)
        assert isinstance(result, np.ndarray)
        assert result.shape[0] == 3
        assert result.shape[1] == 384

    def test_custom_batch_size(self, embedding_service):
        """Test custom batch size."""
        texts = [f"Text {i}" for i in range(10)]
        result = embedding_service.generate_embeddings(texts, batch_size=5)
        assert result.shape[0] == 10
        assert result.shape[1] == 384

    @patch('coderabbit_ai.embeddings.SentenceTransformer')
    def test_embedding_generation_success(self, mock_transformer, embedding_service):
        """Test successful embedding generation."""
        mock_model = Mock()
        mock_model.encode.return_value = np.random.rand(2, 384).astype(np.float32)
        mock_transformer.return_value = mock_model

        service = EmbeddingService(model_name="all-MiniLM-L6-v2", device="cpu")
        texts = ["Text 1", "Text 2"]
        result = service.generate_embeddings(texts)

        mock_model.encode.assert_called_once()
        assert result.shape == (2, 384)


class TestEmbeddingNormalization:
    """Test suite for embedding normalization."""

    @patch('coderabbit_ai.embeddings.SentenceTransformer')
    def test_l2_normalization(self, mock_transformer, embedding_service):
        """Test that embeddings are L2 normalized."""
        mock_model = Mock()
        mock_model.encode.return_value = np.random.rand(2, 384).astype(np.float32)
        mock_transformer.return_value = mock_model

        service = EmbeddingService(model_name="all-MiniLM-L6-v2", device="cpu")
        texts = ["Text 1", "Text 2"]
        embeddings = service.generate_embeddings(texts)

        # Check L2 norm (should be approximately 1.0)
        for embedding in embeddings:
            norm = np.linalg.norm(embedding)
            assert 0.9 < norm < 1.1, f"Embedding norm {norm} should be close to 1.0"


class TestDimensionValidation:
    """Test suite for dimension validation."""

    def test_correct_dimensions(self, embedding_service):
        """Test correct dimensions for all models."""
        for model, expected_dim in EmbeddingService.MODELS.items():
            service = EmbeddingService(model_name=model, device="cpu")
            assert service.dimension == expected_dim

    def test_embedding_output_shape(self, embedding_service):
        """Test that output shape matches dimension."""
        texts = ["Test text"] * 3
        result = embedding_service.generate_embeddings(texts)
        assert result.shape == (3, 384)


class TestErrorHandling:
    """Test suite for error handling."""

    @patch('coderabbit_ai.embeddings.SentenceTransformer')
    def test_model_load_failure(self, mock_transformer):
        """Test handling of model load failure."""
        mock_transformer.side_effect = Exception("Model load failed")
        
        with pytest.raises(Exception, match="Model load failed"):
            EmbeddingService(model_name="all-MiniLM-L6-v2", device="cpu")

    @patch('coderabbit_ai.embeddings.SentenceTransformer')
    def test_generation_failure(self, mock_transformer):
        """Test handling of embedding generation failure."""
        mock_model = Mock()
        mock_model.encode.side_effect = Exception("Generation failed")
        mock_transformer.return_value = mock_model

        service = EmbeddingService(model_name="all-MiniLM-L6-v2", device="cpu")
        texts = ["Test text"]

        with pytest.raises(Exception, match="Generation failed"):
            service.generate_embeddings(texts)


class TestEnvironmentVariables:
    """Test suite for environment variable configuration."""

    @patch.dict(os.environ, {"EMBEDDING_MODEL": "all-mpnet-base-v2"})
    def test_model_from_env(self):
        """Test loading model from environment variable."""
        service = EmbeddingService()
        assert service.model_name == "all-mpnet-base-v2"

    @patch.dict(os.environ, {"EMBEDDING_MODEL": "custom-model"})
    @patch('coderabbit_ai.embeddings.SentenceTransformer')
    def test_custom_model_from_env(self, mock_transformer):
        """Test custom model from environment variable."""
        mock_model = Mock()
        mock_model.encode.return_value = np.random.rand(1, 384).astype(np.float32)
        mock_transformer.return_value = mock_model

        service = EmbeddingService()
        assert service.model_name == "custom-model"
        service.generate_embeddings(["Test"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
