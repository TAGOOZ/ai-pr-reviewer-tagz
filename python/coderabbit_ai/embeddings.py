"""Embedding generation service using sentence-transformers."""

import os
import numpy as np
from typing import List, Optional
from loguru import logger
from sentence_transformers import SentenceTransformer
import torch


class EmbeddingService:
    """Service for generating code embeddings using transformer models."""

    # Supported models with their dimensions
    MODELS = {
        "all-MiniLM-L6-v2": 384,  # Fast, small model
        "all-mpnet-base-v2": 768,  # Best quality
        "codebert-base": 768,  # Code-specific
        "graphcodebert-base": 768,  # Code-specific with data flow
    }

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        """
        Initialize the embedding service.

        Args:
            model_name: Name of the model to use (defaults to all-MiniLM-L6-v2)
            device: Device to run on ('cuda', 'cpu', or None for auto-detect)
        """
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

        if self.model_name not in self.MODELS:
            logger.warning(f"Unknown model {self.model_name}, falling back to all-MiniLM-L6-v2")
            self.model_name = "all-MiniLM-L6-v2"

        # Determine device
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        # Load model
        logger.info(f"Loading embedding model: {self.model_name} on {self.device}")
        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.dimension = self.MODELS[self.model_name]
            logger.info(f"Model loaded successfully. Embedding dimension: {self.dimension}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for processing

        Returns:
            NumPy array of shape (len(texts), embedding_dimension)
        """
        if not texts:
            return np.array([])

        logger.info(f"Generating embeddings for {len(texts)} texts with batch_size={batch_size}")

        try:
            # Generate embeddings in batches
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=len(texts) > 100,
                convert_to_numpy=True,
                normalize_embeddings=True  # L2 normalization for cosine similarity
            )

            logger.info(f"Generated {len(embeddings)} embeddings of dimension {embeddings.shape[1]}")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def generate_single_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            NumPy array of shape (embedding_dimension,)
        """
        embeddings = self.generate_embeddings([text], batch_size=1)
        return embeddings[0]

    def generate_code_embeddings(
        self,
        code_snippets: List[str],
        batch_size: int = 32,
        prefix: str = "code: "
    ) -> np.ndarray:
        """
        Generate embeddings specifically for code snippets.

        Args:
            code_snippets: List of code strings
            batch_size: Batch size for processing
            prefix: Prefix to add to code (helps model understand it's code)

        Returns:
            NumPy array of embeddings
        """
        # Add prefix to help model understand this is code
        prefixed_snippets = [f"{prefix}{code}" for code in code_snippets]
        return self.generate_embeddings(prefixed_snippets, batch_size=batch_size)

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        # Embeddings are already normalized, so dot product = cosine similarity
        similarity = np.dot(embedding1, embedding2)
        return float(similarity)

    def compute_similarities_batch(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute similarities between a query and multiple candidates.

        Args:
            query_embedding: Query embedding of shape (dimension,)
            candidate_embeddings: Candidate embeddings of shape (n, dimension)

        Returns:
            Array of similarity scores of shape (n,)
        """
        # Matrix multiplication for batch similarity computation
        similarities = np.dot(candidate_embeddings, query_embedding)
        return similarities

    @property
    def embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        return self.dimension

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "device": self.device,
            "max_seq_length": self.model.max_seq_length if hasattr(self.model, 'max_seq_length') else None
        }


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = EmbeddingService()

    return _embedding_service


def reset_embedding_service():
    """Reset the global embedding service (useful for testing)."""
    global _embedding_service
    _embedding_service = None
