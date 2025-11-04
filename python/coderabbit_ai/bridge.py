"""Bridge to Rust-based static analyzer and other Rust services."""

import subprocess
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def call_static_analyzer(file_path: str, language: str, content: str) -> Optional[Dict[str, Any]]:
    """
    Call the Rust-based static analyzer.
    
    Args:
        file_path: Path to the file being analyzed
        language: Programming language of the file
        content: File content to analyze
        
    Returns:
        Dictionary with analysis results or None if analysis fails
    """
    try:
        # Prepare input for the analyzer
        input_data = {
            "file_path": file_path,
            "language": language,
            "content": content
        }
        
        # Call the Rust analyzer (assuming it's compiled and in PATH)
        # In production, this would call the actual crates/code-analyzer binary
        result = subprocess.run(
            ['cargo', 'run', '--bin', 'code-analyzer', '--quiet'],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        else:
            logger.warning(f"Static analyzer returned error for {file_path}: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error(f"Static analyzer timed out for {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse static analyzer output: {e}")
        return None
    except Exception as e:
        logger.error(f"Static analyzer failed for {file_path}: {e}")
        return None


def call_embedding_service(text: str) -> Optional[List[float]]:
    """
    Call the embedding service to generate embeddings.
    
    Args:
        text: Text to embed
        
    Returns:
        List of embedding values or None if generation fails
    """
    try:
        # Call the embedding service (assuming it's running on localhost:8081)
        import requests
        
        response = requests.post(
            'http://localhost:8081/embed',
            json={'text': text},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('embedding')
        else:
            logger.warning(f"Embedding service returned status {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call embedding service: {e}")
        return None
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


def call_vector_search(query_embedding: List[float], top_k: int = 5) -> Optional[List[Dict[str, Any]]]:
    """
    Call the vector search engine to find similar code.
    
    Args:
        query_embedding: Query embedding vector
        top_k: Number of results to return
        
    Returns:
        List of similar code snippets or None if search fails
    """
    try:
        import requests
        
        response = requests.post(
            'http://localhost:8082/search',
            json={
                'embedding': query_embedding,
                'top_k': top_k
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('results', [])
        else:
            logger.warning(f"Vector search returned status {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call vector search: {e}")
        return None
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return None


def call_code_analyzer_embeddings(code: str) -> Optional[List[float]]:
    """
    Call the code analyzer to extract embeddings.
    
    This is a convenience function that combines embedding generation
    with the code analyzer service.
    
    Args:
        code: Code to analyze and embed
        
    Returns:
        Embedding vector or None if generation fails
    """
    try:
        # First try the dedicated embedding service
        embedding = call_embedding_service(code)
        if embedding:
            return embedding
        
        # Fallback to local embedding generation
        from .embeddings import EmbeddingService
        service = EmbeddingService()
        return service.generate_embedding(code)
        
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        return None
