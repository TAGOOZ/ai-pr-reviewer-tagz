use crate::storage::{VectorRecord, VectorStorage};
use anyhow::anyhow;
use coderabbit_shared::Result;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub content: String,
    pub similarity_score: f32,
    pub metadata: HashMap<String, String>,
    pub id: String,
    pub file_path: Option<String>,
}

pub struct VectorEngine {
    storage: VectorStorage,
    http_client: Client,
    embedding_service_url: String,
    embedding_model: Option<String>,
}

impl VectorEngine {
    pub async fn new() -> Result<Self> {
        let storage = VectorStorage::new("code_vectors").await?;
        let embedding_model =
            std::env::var("EMBEDDING_MODEL").unwrap_or_else(|_| "all-MiniLM-L6-v2".to_string());

        let embedding_service_url = std::env::var("EMBEDDING_SERVICE_URL")
            .unwrap_or_else(|_| "http://localhost:8081".to_string());

        let http_client = Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .map_err(|e| anyhow!(e))?;

        tracing::info!(
            "Initialized Vector Engine with embedding model: {} at {}",
            embedding_model,
            embedding_service_url
        );
        Ok(Self {
            storage,
            embedding_model: Some(embedding_model),
            http_client,
            embedding_service_url,
        })
    }

    pub async fn generate_embeddings(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }

        tracing::info!(
            "Generating embeddings for {} texts using Python service",
            texts.len()
        );

        // Try to call Python embedding service first
        match self.generate_embeddings_via_service(&texts).await {
            Ok(embeddings) => {
                tracing::info!(
                    "Generated {} embeddings via Python service",
                    embeddings.len()
                );
                Ok(embeddings)
            }
            Err(e) => {
                tracing::warn!("Failed to generate embeddings via Python service: {}. Falling back to hash-based embeddings.", e);
                // Fall back to hash-based embeddings if service is unavailable
                let mut embeddings = Vec::with_capacity(texts.len());
                for text in texts {
                    let embedding = self.generate_simple_embedding(&text)?;
                    embeddings.push(embedding);
                }
                Ok(embeddings)
            }
        }
    }

    /// Generate embeddings via Python service HTTP endpoint
    async fn generate_embeddings_via_service(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        #[derive(Serialize)]
        struct EmbeddingRequest {
            code_snippets: Vec<String>,
            batch_size: u32,
        }

        let request = EmbeddingRequest {
            code_snippets: texts.to_vec(),
            batch_size: 32,
        };

        let url = format!("{}/bridge/embedding_batch", self.embedding_service_url);

        let response = self
            .http_client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| anyhow!(e))?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(anyhow!("Embedding service returned {}: {}", status, error_text).into());
        }

        let embeddings: Vec<Vec<f32>> = response.json().await.map_err(|e| anyhow!(e))?;
        Ok(embeddings)
    }

    /// Simple hash-based embedding for fallback when service is unavailable
    fn generate_simple_embedding(&self, text: &str) -> Result<Vec<f32>> {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        text.hash(&mut hasher);
        let hash_value = hasher.finish();

        let mut embedding = vec![0.0; 384]; // Match Python service default dimension
        for i in 0..384 {
            let mixed_hash = (hash_value.wrapping_mul(0x9e3779b97f4a7c15) ^ (i as u64)) as u32;
            let value = (mixed_hash as f32 / u32::MAX as f32) * 2.0 - 1.0;
            embedding[i] = value;
        }

        // Normalize the vector
        let norm: f32 = embedding.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 0.0 {
            for value in &mut embedding {
                *value /= norm;
            }
        }

        Ok(embedding)
    }

    pub async fn similarity_search(&self, query: &[f32], k: usize) -> Result<Vec<SearchResult>> {
        tracing::info!(
            "Performing similarity search with k={}, vector dimension: {}",
            k,
            query.len()
        );

        // Use LanceDB to find similar vectors
        let results = self.storage.query(query, k, None).await?;

        let search_results: Vec<SearchResult> = results
            .into_iter()
            .map(|record| {
                let similarity = self.cosine_similarity(query, &record.embedding);
                let metadata = HashMap::from([
                    (
                        "language".to_string(),
                        record.metadata.get("language").cloned().unwrap_or_default(),
                    ),
                    (
                        "file_path".to_string(),
                        record
                            .metadata
                            .get("file_path")
                            .cloned()
                            .unwrap_or_default(),
                    ),
                ]);

                SearchResult {
                    content: record.content,
                    similarity_score: similarity,
                    metadata,
                    id: record.id,
                    file_path: record.metadata.get("file_path").cloned(),
                }
            })
            .collect();

        // Sort by similarity score (highest first)
        let mut sorted_results = search_results;
        sorted_results.sort_by(|a, b| {
            b.similarity_score
                .partial_cmp(&a.similarity_score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        Ok(sorted_results)
    }

    /// Calculate cosine similarity between two vectors
    fn cosine_similarity(&self, a: &[f32], b: &[f32]) -> f32 {
        let dot_product: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();

        if norm_a == 0.0 || norm_b == 0.0 {
            0.0
        } else {
            dot_product / (norm_a * norm_b)
        }
    }

    pub async fn batch_insert(
        &self,
        items: Vec<(String, Vec<f32>, HashMap<String, String>)>,
        contents: Vec<String>,
    ) -> Result<()> {
        tracing::info!("Batch inserting {} items into vector storage", items.len());

        let records: Vec<VectorRecord> = VectorStorage::build_records(items, contents);
        self.storage.batch_insert(records).await?;

        Ok(())
    }

    pub async fn create_index(&self, dimension: usize) -> Result<String> {
        tracing::info!("Creating vector index with dimension: {}", dimension);

        self.storage.create_index("embedding", "disk_ann").await?;
        let index_id = format!(
            "embedding_index_{}_{}",
            dimension,
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs()
        );

        Ok(index_id)
    }

    pub async fn delete_by_metadata(&self, filter: HashMap<String, String>) -> Result<u64> {
        tracing::info!("Deleting vectors by metadata filter: {:?}", filter);

        // This is a simplified implementation
        // In production, you'd want to use more sophisticated filtering
        let results = self
            .storage
            .query(&vec![0.0; 1536], 10000, Some(filter.clone()))
            .await?;

        let mut deleted_count = 0;
        for record in results {
            self.storage.delete(&record.id).await?;
            deleted_count += 1;
        }

        Ok(deleted_count)
    }

    pub async fn get_stats(&self) -> Result<VectorStats> {
        let storage_stats = self.storage.get_stats().await?;

        Ok(VectorStats {
            total_vectors: storage_stats.total_records,
            index_size_bytes: storage_stats.index_size_bytes,
            dimensions: 1536,
        })
    }

    /// Search for code similar to the provided query code
    pub async fn search_code_context(
        &self,
        query_code: &str,
        language: &str,
        k: usize,
    ) -> Result<Vec<SearchResult>> {
        // Generate embedding for query code
        let query_embedding = self.generate_simple_embedding(query_code)?;

        // Add language filter
        let filters = HashMap::from([("language".to_string(), language.to_string())]);

        // Search in LanceDB
        let results = self
            .storage
            .query(&query_embedding, k, Some(filters))
            .await?;

        let search_results: Vec<SearchResult> = results
            .into_iter()
            .map(|record| {
                let similarity = self.cosine_similarity(&query_embedding, &record.embedding);
                let metadata = HashMap::from([
                    (
                        "language".to_string(),
                        record.metadata.get("language").cloned().unwrap_or_default(),
                    ),
                    (
                        "file_path".to_string(),
                        record
                            .metadata
                            .get("file_path")
                            .cloned()
                            .unwrap_or_default(),
                    ),
                ]);

                SearchResult {
                    content: record.content,
                    similarity_score: similarity,
                    metadata,
                    id: record.id,
                    file_path: record.metadata.get("file_path").cloned(),
                }
            })
            .collect();

        Ok(search_results)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorStats {
    pub total_vectors: u64,
    pub index_size_bytes: u64,
    pub dimensions: usize,
}
