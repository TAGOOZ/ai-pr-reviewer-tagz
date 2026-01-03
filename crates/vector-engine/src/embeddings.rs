use coderabbit_shared::{CodeRabbitError, Result};
// use candle_core::{Device, Tensor}; // Commented out for initial setup
use reqwest::Client;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize)]
struct EmbeddingRequest {
    input: Vec<String>,
    model: String,
}

#[derive(Debug, Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingData>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
}

pub struct EmbeddingGenerator {
    client: Client,
    api_key: String,
    model: String,
}

impl EmbeddingGenerator {
    pub fn new(api_key: String) -> Self {
        Self {
            client: Client::new(),
            api_key,
            model: "text-embedding-3-small".to_string(),
        }
    }

    pub async fn generate_embeddings(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        tracing::info!(
            "Generating embeddings for {} texts using OpenAI API",
            texts.len()
        );

        let request = EmbeddingRequest {
            input: texts,
            model: self.model.clone(),
        };

        // Call OpenAI API
        let response = self
            .client
            .post("https://api.openai.com/v1/embeddings")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| {
                CodeRabbitError::ExternalAPIError(format!("OpenAI API request failed: {}", e))
            })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::ExternalAPIError(format!(
                "OpenAI API returned status {}: {}",
                status, error_text
            )));
        }

        let embedding_response: EmbeddingResponse = response.json().await.map_err(|e| {
            CodeRabbitError::ExternalAPIError(format!("Failed to parse OpenAI response: {}", e))
        })?;

        let embeddings = embedding_response
            .data
            .into_iter()
            .map(|d| d.embedding)
            .collect();

        Ok(embeddings)
    }

    pub async fn generate_code_embeddings(
        &self,
        code_snippets: Vec<String>,
    ) -> Result<Vec<Vec<f32>>> {
        // Preprocess code snippets for better embedding quality
        let preprocessed: Vec<String> = code_snippets
            .iter()
            .map(|code| {
                // Add code-specific context
                format!("Code snippet:\n{}", code)
            })
            .collect();

        self.generate_embeddings(preprocessed).await
    }

    pub async fn generate_embeddings_chunked(
        &self,
        texts: Vec<String>,
        chunk_size: usize,
    ) -> Result<Vec<Vec<f32>>> {
        if chunk_size == 0 {
            return Err(CodeRabbitError::ConfigError(
                "chunk_size must be > 0".to_string(),
            ));
        }

        let mut all_embeddings: Vec<Vec<f32>> = Vec::with_capacity(texts.len());
        let mut start = 0;
        while start < texts.len() {
            let end = (start + chunk_size).min(texts.len());
            let batch = texts[start..end].to_vec();
            let mut batch_embeddings = self.generate_embeddings(batch).await?;
            all_embeddings.append(&mut batch_embeddings);
            start = end;
        }

        Ok(all_embeddings)
    }

    pub fn cosine_similarity(&self, a: &[f32], b: &[f32]) -> f32 {
        if a.len() != b.len() {
            return 0.0;
        }

        let dot_product: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();

        if norm_a == 0.0 || norm_b == 0.0 {
            0.0
        } else {
            dot_product / (norm_a * norm_b)
        }
    }
}

/// Cohere API request/response types
#[derive(Debug, Serialize)]
struct CohereEmbeddingRequest {
    texts: Vec<String>,
    model: String,
    input_type: String,
}

#[derive(Debug, Deserialize)]
struct CohereEmbeddingResponse {
    embeddings: Vec<Vec<f32>>,
}

/// Cohere Embeddings API client
pub struct CohereEmbeddings {
    client: Client,
    api_key: String,
    model: String,
}

impl CohereEmbeddings {
    pub fn new(api_key: String) -> Self {
        Self {
            client: Client::new(),
            api_key,
            model: "embed-english-v3.0".to_string(),
        }
    }

    pub fn with_model(mut self, model: String) -> Self {
        self.model = model;
        self
    }

    pub async fn generate_embeddings(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        tracing::info!(
            "Generating embeddings for {} texts using Cohere API",
            texts.len()
        );

        let request = CohereEmbeddingRequest {
            texts,
            model: self.model.clone(),
            input_type: "search_document".to_string(),
        };

        let response = self
            .client
            .post("https://api.cohere.ai/v1/embed")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| {
                CodeRabbitError::ExternalAPIError(format!("Cohere API request failed: {}", e))
            })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::ExternalAPIError(format!(
                "Cohere API returned status {}: {}",
                status, error_text
            )));
        }

        let embedding_response: CohereEmbeddingResponse = response.json().await.map_err(|e| {
            CodeRabbitError::ExternalAPIError(format!("Failed to parse Cohere response: {}", e))
        })?;

        Ok(embedding_response.embeddings)
    }

    pub async fn generate_code_embeddings(
        &self,
        code_snippets: Vec<String>,
    ) -> Result<Vec<Vec<f32>>> {
        // Preprocess code snippets for better embedding quality
        let preprocessed: Vec<String> = code_snippets
            .iter()
            .map(|code| {
                // Add code-specific context
                format!("Code snippet:\n{}", code)
            })
            .collect();

        self.generate_embeddings(preprocessed).await
    }

    pub async fn generate_query_embeddings(&self, queries: Vec<String>) -> Result<Vec<Vec<f32>>> {
        tracing::info!(
            "Generating query embeddings for {} queries using Cohere API",
            queries.len()
        );

        let request = CohereEmbeddingRequest {
            texts: queries,
            model: self.model.clone(),
            input_type: "search_query".to_string(), // Use search_query for queries
        };

        let response = self
            .client
            .post("https://api.cohere.ai/v1/embed")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| {
                CodeRabbitError::ExternalAPIError(format!("Cohere API request failed: {}", e))
            })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::ExternalAPIError(format!(
                "Cohere API returned status {}: {}",
                status, error_text
            )));
        }

        let embedding_response: CohereEmbeddingResponse = response.json().await.map_err(|e| {
            CodeRabbitError::ExternalAPIError(format!("Failed to parse Cohere response: {}", e))
        })?;

        Ok(embedding_response.embeddings)
    }

    pub async fn generate_embeddings_chunked(
        &self,
        texts: Vec<String>,
        chunk_size: usize,
    ) -> Result<Vec<Vec<f32>>> {
        if chunk_size == 0 {
            return Err(CodeRabbitError::ConfigError(
                "chunk_size must be > 0".to_string(),
            ));
        }

        let mut all_embeddings: Vec<Vec<f32>> = Vec::with_capacity(texts.len());
        let mut start = 0;
        while start < texts.len() {
            let end = (start + chunk_size).min(texts.len());
            let batch = texts[start..end].to_vec();
            let mut batch_embeddings = self.generate_embeddings(batch).await?;
            all_embeddings.append(&mut batch_embeddings);
            start = end;
        }

        Ok(all_embeddings)
    }

    pub fn cosine_similarity(&self, a: &[f32], b: &[f32]) -> f32 {
        if a.len() != b.len() {
            return 0.0;
        }

        let dot_product: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();

        if norm_a == 0.0 || norm_b == 0.0 {
            0.0
        } else {
            dot_product / (norm_a * norm_b)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_embedding_generator_creation() {
        let gen = EmbeddingGenerator::new("test_api_key".to_string());
        assert_eq!(gen.api_key, "test_api_key");
        assert_eq!(gen.model, "text-embedding-3-small");
    }

    #[test]
    fn test_cosine_similarity_identical_vectors() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        let vec = vec![1.0, 2.0, 3.0, 4.0];

        let similarity = gen.cosine_similarity(&vec, &vec);
        assert!((similarity - 1.0).abs() < 0.0001);
    }

    #[test]
    fn test_cosine_similarity_orthogonal_vectors() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        let vec_a = vec![1.0, 0.0];
        let vec_b = vec![0.0, 1.0];

        let similarity = gen.cosine_similarity(&vec_a, &vec_b);
        assert!((similarity - 0.0).abs() < 0.0001);
    }

    #[test]
    fn test_cosine_similarity_opposite_vectors() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        let vec_a = vec![1.0, 2.0, 3.0];
        let vec_b = vec![-1.0, -2.0, -3.0];

        let similarity = gen.cosine_similarity(&vec_a, &vec_b);
        assert!((similarity - (-1.0)).abs() < 0.0001);
    }

    #[test]
    fn test_cosine_similarity_different_lengths() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        let vec_a = vec![1.0, 2.0, 3.0];
        let vec_b = vec![1.0, 2.0];

        let similarity = gen.cosine_similarity(&vec_a, &vec_b);
        assert_eq!(similarity, 0.0);
    }

    #[test]
    fn test_cosine_similarity_zero_vector() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        let vec_a = vec![1.0, 2.0, 3.0];
        let vec_b = vec![0.0, 0.0, 0.0];

        let similarity = gen.cosine_similarity(&vec_a, &vec_b);
        assert_eq!(similarity, 0.0);
    }

    #[test]
    fn test_cosine_similarity_normalized_vectors() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        // Unit vectors at 45 degrees
        let vec_a = vec![1.0, 0.0];
        let vec_b = vec![0.707, 0.707];

        let similarity = gen.cosine_similarity(&vec_a, &vec_b);
        assert!((similarity - 0.707).abs() < 0.01);
    }

    #[tokio::test]
    async fn test_chunked_embeddings_zero_chunk_size() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        let texts = vec!["text1".to_string()];

        let result = gen.generate_embeddings_chunked(texts, 0).await;
        assert!(result.is_err());

        if let Err(CodeRabbitError::ConfigError(msg)) = result {
            assert!(msg.contains("chunk_size must be > 0"));
        } else {
            panic!("Expected ConfigError");
        }
    }

    #[test]
    fn test_embedding_request_serialization() {
        let request = EmbeddingRequest {
            input: vec!["test".to_string()],
            model: "text-embedding-3-small".to_string(),
        };

        let json = serde_json::to_string(&request).unwrap();
        assert!(json.contains("test"));
        assert!(json.contains("text-embedding-3-small"));
    }

    #[test]
    fn test_embedding_response_deserialization() {
        let json = r#"{
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]}
            ]
        }"#;

        let response: EmbeddingResponse = serde_json::from_str(json).unwrap();
        assert_eq!(response.data.len(), 2);
        assert_eq!(response.data[0].embedding, vec![0.1, 0.2, 0.3]);
        assert_eq!(response.data[1].embedding, vec![0.4, 0.5, 0.6]);
    }

    #[test]
    fn test_large_vector_cosine_similarity() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        // Test with 1536-dimensional vectors (OpenAI embedding size)
        let vec_a: Vec<f32> = (0..1536).map(|i| i as f32 / 1536.0).collect();
        let vec_b: Vec<f32> = (0..1536).map(|i| i as f32 / 1536.0).collect();

        let similarity = gen.cosine_similarity(&vec_a, &vec_b);
        assert!((similarity - 1.0).abs() < 0.0001);
    }

    #[test]
    fn test_cosine_similarity_performance() {
        let gen = EmbeddingGenerator::new("test_key".to_string());
        let vec_a: Vec<f32> = (0..1536).map(|i| (i as f32).sin()).collect();
        let vec_b: Vec<f32> = (0..1536).map(|i| (i as f32).cos()).collect();

        // Just verify it completes without panic
        let similarity = gen.cosine_similarity(&vec_a, &vec_b);
        assert!(similarity >= -1.0 && similarity <= 1.0);
    }

    // Note: Tests that require actual API calls should be integration tests
    // and should be run with proper API keys and marked as #[ignore] by default

    #[tokio::test]
    #[ignore] // Requires valid OpenAI API key
    async fn integration_test_generate_embeddings() {
        let api_key = std::env::var("OPENAI_API_KEY").unwrap_or_default();
        if api_key.is_empty() {
            return; // Skip if no API key
        }

        let gen = EmbeddingGenerator::new(api_key);
        let texts = vec!["Hello world".to_string()];

        let result = gen.generate_embeddings(texts).await;
        assert!(result.is_ok());

        let embeddings = result.unwrap();
        assert_eq!(embeddings.len(), 1);
        assert!(!embeddings[0].is_empty());
    }
}
