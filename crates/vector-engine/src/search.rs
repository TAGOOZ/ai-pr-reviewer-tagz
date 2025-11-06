use crate::engine::SearchResult;
use crate::storage::VectorStorage;
use coderabbit_shared::Result;
use std::collections::HashMap;
use std::sync::Arc;

pub struct SemanticSearch {
    storage: Arc<VectorStorage>,
}

impl SemanticSearch {
    pub async fn new(table_name: &str) -> Result<Self> {
        let storage = VectorStorage::new(table_name).await?;
        Ok(Self {
            storage: Arc::new(storage),
        })
    }

    pub async fn initialize(&self) -> Result<()> {
        tracing::info!("SemanticSearch initialized with VectorStorage");
        Ok(())
    }

    pub async fn search_similar_code(&self, query_embedding: &[f32], k: usize, filters: Option<HashMap<String, String>>) -> Result<Vec<SearchResult>> {
        tracing::info!("Searching for similar code with k={}, filters={:?}", k, filters);

        // Use VectorStorage to perform the actual search
        let records = self.storage.query(query_embedding, k, filters).await?;

        // Convert VectorRecord to SearchResult
        let results: Vec<SearchResult> = records
            .into_iter()
            .map(|record| {
                let similarity = self.cosine_similarity(query_embedding, &record.embedding);
                SearchResult {
                    content: record.content,
                    similarity_score: similarity,
                    metadata: record.metadata.clone(),
                    id: record.id,
                    file_path: record.metadata.get("file_path").cloned(),
                }
            })
            .collect();

        Ok(results)
    }

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

    pub async fn search_by_text(&self, query: &str, k: usize) -> Result<Vec<SearchResult>> {
        tracing::info!("Searching by text query: '{}' with k={}", query, k);
        
        // Generate embedding for the text query
        let embedding = self.generate_query_embedding(query).await?;
        
        // Use vector search with the generated embedding
        self.search_similar_code(&embedding, k, None).await
    }
    
    async fn generate_query_embedding(&self, query: &str) -> Result<Vec<f32>> {
        // Call embedding service
        let embedding_url = std::env::var("EMBEDDING_SERVICE_URL")
            .unwrap_or_else(|_| "http://localhost:8081/embed".to_string());
        
        let client = reqwest::Client::new();
        
        #[derive(serde::Serialize)]
        struct EmbeddingRequest {
            text: String,
        }
        
        #[derive(serde::Deserialize)]
        struct EmbeddingResponse {
            embedding: Vec<f32>,
        }
        
        let response = client
            .post(&embedding_url)
            .json(&EmbeddingRequest {
                text: query.to_string(),
            })
            .send()
            .await
            .map_err(|e| anyhow::anyhow!("Failed to call embedding service: {}", e))?;
        
        let data: EmbeddingResponse = response.json().await
            .map_err(|e| anyhow::anyhow!("Failed to parse embedding response: {}", e))?;
        
        Ok(data.embedding)
    }

    pub async fn search_related_issues(&self, code_embedding: &[f32], repository_id: &str) -> Result<Vec<SearchResult>> {
        let mut filters = HashMap::new();
        filters.insert("repository_id".to_string(), repository_id.to_string());
        filters.insert("type".to_string(), "issue".to_string());
        
        self.search_similar_code(code_embedding, 10, Some(filters)).await
    }

    pub async fn search_similar_patterns(&self, code_embedding: &[f32], language: &str) -> Result<Vec<SearchResult>> {
        let mut filters = HashMap::new();
        filters.insert("language".to_string(), language.to_string());
        filters.insert("type".to_string(), "pattern".to_string());
        
        self.search_similar_code(code_embedding, 5, Some(filters)).await
    }

    pub async fn hybrid_search(&self, text_query: &str, code_embedding: &[f32], k: usize) -> Result<Vec<SearchResult>> {
        tracing::info!("Performing parallel hybrid search for: '{}'", text_query);

        // Run text and vector search in parallel for 2x speedup
        let (text_result, vector_result) = tokio::join!(
            self.search_by_text(text_query, k / 2),
            self.search_similar_code(code_embedding, k / 2, None)
        );

        // Handle errors from parallel execution
        let text_results = text_result?;
        let vector_results = vector_result?;

        // Merge and re-rank results
        let combined_results = self.merge_and_rerank(text_results, vector_results, text_query);

        Ok(combined_results)
    }
    
    fn merge_and_rerank(&self, mut text_results: Vec<SearchResult>, mut vector_results: Vec<SearchResult>, _query: &str) -> Vec<SearchResult> {
        // Create a map to deduplicate results
        let mut result_map: HashMap<String, SearchResult> = HashMap::new();
        
        // Add text results with boosted scores
        for (idx, mut result) in text_results.into_iter().enumerate() {
            result.similarity_score = 1.0 - (idx as f32 * 0.1); // Decay score
            result_map.insert(result.id.clone(), result);
        }
        
        // Merge vector results
        for (idx, mut result) in vector_results.into_iter().enumerate() {
            let score = 0.8 - (idx as f32 * 0.08); // Slightly lower base score
            if let Some(existing) = result_map.get_mut(&result.id) {
                // Boost score if found in both
                existing.similarity_score = (existing.similarity_score + score) / 2.0 * 1.2;
            } else {
                result.similarity_score = score;
                result_map.insert(result.id.clone(), result);
            }
        }

        // Convert back to vector and sort by score
        let mut results: Vec<SearchResult> = result_map.into_values().collect();
        results.sort_by(|a, b| b.similarity_score.partial_cmp(&a.similarity_score).unwrap_or(std::cmp::Ordering::Equal));
        
        results
    }

    /// Add a code snippet to the vector index
    pub async fn add_code(&self, id: String, content: String, embedding: Vec<f32>, metadata: HashMap<String, String>) -> Result<()> {
        use crate::storage::VectorRecord;

        let record = VectorRecord {
            id,
            content,
            embedding,
            metadata,
            created_at: chrono::Utc::now(),
        };

        self.storage.insert(record).await
    }

    /// Update existing code in the vector index
    pub async fn update_code(&self, id: &str, content: String, embedding: Vec<f32>, metadata: HashMap<String, String>) -> Result<()> {
        use crate::storage::VectorRecord;

        let record = VectorRecord {
            id: id.to_string(),
            content,
            embedding,
            metadata,
            created_at: chrono::Utc::now(),
        };

        self.storage.update(id, record).await
    }

    /// Delete code from the vector index
    pub async fn delete_code(&self, id: &str) -> Result<()> {
        self.storage.delete(id).await
    }
}