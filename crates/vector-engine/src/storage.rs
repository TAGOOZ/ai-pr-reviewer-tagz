use coderabbit_shared::{CodeRabbitError, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorRecord {
    pub id: String,
    pub content: String,
    pub embedding: Vec<f32>,
    pub metadata: HashMap<String, String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RAGSearchResult {
    pub record: VectorRecord,
    pub similarity_score: f32,
    pub textual_relevance: f32,
    pub relevance_score: f32,
    pub chunk_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HybridSearchResult {
    pub record: VectorRecord,
    pub similarity_score: f32,
    pub keyword_score: f32,
    pub hybrid_score: f32,
    pub source_type: String, // "vector", "keyword", or "hybrid"
}

#[derive(Debug)]
pub struct VectorStorage {
    // Enhanced LanceDB integration with RAG capabilities
    records: Arc<RwLock<HashMap<String, VectorRecord>>>,
    index_stats: Arc<RwLock<IndexStats>>,
    rag_enabled: bool,
    max_results: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexStats {
    pub total_records: u64,
    pub storage_size_bytes: u64,
    pub index_size_bytes: u64,
    pub last_optimized: Option<chrono::DateTime<chrono::Utc>>,
    pub query_count: u64,
    pub avg_query_time_ms: f64,
}

impl VectorStorage {
    pub async fn new(table_name: &str) -> Result<Self> {
        tracing::info!(
            "Initializing LanceDB vector storage for table: {}",
            table_name
        );

        // Initialize in-memory storage with LanceDB-like structure
        let storage = Self {
            records: Arc::new(RwLock::new(HashMap::new())),
            index_stats: Arc::new(RwLock::new(IndexStats {
                total_records: 0,
                storage_size_bytes: 0,
                index_size_bytes: 0,
                last_optimized: Some(chrono::Utc::now()),
                query_count: 0,
                avg_query_time_ms: 0.0,
            })),
            rag_enabled: true,
            max_results: 1000,
        };

        // Simulate LanceDB table creation
        storage.create_lance_table(table_name).await?;

        Ok(storage)
    }

    /// Create and configure LanceDB table
    async fn create_lance_table(&self, table_name: &str) -> Result<()> {
        tracing::info!("Creating LanceDB table '{}' with vector schema", table_name);

        // In a real implementation, this would:
        // 1. Connect to LanceDB
        // 2. Create a table with vector and metadata columns
        // 3. Configure indexes for efficient similarity search

        let mut stats = self.index_stats.write().await;
        stats.storage_size_bytes = 1024 * 1024; // 1MB initial allocation

        Ok(())
    }

    pub async fn insert(&self, record: VectorRecord) -> Result<()> {
        tracing::info!("Inserting vector record with ID: {}", record.id);

        // Calculate approximate storage size
        let record_size = self.calculate_record_size(&record);

        {
            let mut records = self.records.write().await;
            records.insert(record.id.clone(), record);
        }

        // Update stats
        {
            let mut stats = self.index_stats.write().await;
            stats.total_records += 1;
            stats.storage_size_bytes += record_size as u64;
        }

        // Simulate LanceDB async write
        tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;

        Ok(())
    }

    pub async fn batch_insert(&self, records: Vec<VectorRecord>) -> Result<()> {
        tracing::info!(
            "Batch inserting {} vector records into LanceDB",
            records.len()
        );

        if records.is_empty() {
            return Ok(());
        }

        let mut total_size = 0;
        let record_count = records.len();

        {
            let mut storage_records = self.records.write().await;
            let mut stats = self.index_stats.write().await;

            for record in &records {
                let record_size = self.calculate_record_size(record);
                total_size += record_size;

                storage_records.insert(record.id.clone(), record.clone());
                stats.total_records += 1;
            }

            stats.storage_size_bytes += total_size as u64;
        }

        // Optimize after batch insert (LanceDB best practice)
        self.optimize().await?;

        tracing::info!(
            "Batch insert completed. Inserted {} records, {} bytes",
            record_count,
            total_size
        );

        Ok(())
    }

    pub fn build_records(
        items: Vec<(String, Vec<f32>, HashMap<String, String>)>,
        contents: Vec<String>,
    ) -> Vec<VectorRecord> {
        let now = chrono::Utc::now();
        items
            .into_iter()
            .zip(contents.into_iter())
            .map(|((id, embedding, metadata), content)| VectorRecord {
                id,
                content,
                embedding,
                metadata,
                created_at: now,
            })
            .collect()
    }

    pub async fn update(&self, id: &str, record: VectorRecord) -> Result<()> {
        tracing::info!("Updating vector record with ID: {}", id);

        let mut storage_records = self.records.write().await;

        if storage_records.contains_key(id) {
            storage_records.insert(id.to_string(), record);
            tracing::info!("Updated record {}", id);
        } else {
            tracing::warn!("Attempted to update non-existent record: {}", id);
            return Err(CodeRabbitError::Internal(format!(
                "Record {} not found",
                id
            )));
        }

        Ok(())
    }

    pub async fn delete(&self, id: &str) -> Result<()> {
        tracing::info!("Deleting vector record with ID: {}", id);

        let mut storage_records = self.records.write().await;

        if let Some(record) = storage_records.remove(id) {
            let record_size = self.calculate_record_size(&record);

            {
                let mut stats = self.index_stats.write().await;
                stats.total_records = stats.total_records.saturating_sub(1);
                stats.storage_size_bytes =
                    stats.storage_size_bytes.saturating_sub(record_size as u64);
            }

            tracing::info!("Deleted record {} ({} bytes)", id, record_size);
            Ok(())
        } else {
            tracing::warn!("Attempted to delete non-existent record: {}", id);
            Err(CodeRabbitError::NotFound(format!(
                "Record {} not found",
                id
            )))
        }
    }

    pub async fn get(&self, id: &str) -> Result<Option<VectorRecord>> {
        tracing::info!("Retrieving vector record with ID: {}", id);

        let storage_records = self.records.read().await;
        let record = storage_records.get(id).cloned();

        if record.is_some() {
            tracing::info!("Found record {}", id);
        } else {
            tracing::info!("Record {} not found", id);
        }

        Ok(record)
    }

    pub async fn query(
        &self,
        embedding: &[f32],
        limit: usize,
        filters: Option<HashMap<String, String>>,
    ) -> Result<Vec<VectorRecord>> {
        let start_time = std::time::Instant::now();

        tracing::info!(
            "LanceDB similarity query: limit={}, filters={:?}",
            limit,
            filters
        );

        let storage_records = self.records.read().await;
        let mut results: Vec<(VectorRecord, f32)> = Vec::new();

        // Simulate LanceDB vector similarity search
        for record in storage_records.values() {
            // Apply filters first
            if let Some(ref filter) = filters {
                if !self.passes_filter(record, filter) {
                    continue;
                }
            }

            // Calculate cosine similarity
            let similarity = self.cosine_similarity(embedding, &record.embedding);

            results.push((record.clone(), similarity));
        }

        // Sort by similarity score (highest first) and limit results
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        let results: Vec<VectorRecord> = results
            .into_iter()
            .take(limit.min(self.max_results))
            .map(|(record, _)| record)
            .collect();

        // Update query statistics
        {
            let mut stats = self.index_stats.write().await;
            stats.query_count += 1;

            let query_time = start_time.elapsed().as_millis() as f64;
            stats.avg_query_time_ms = (stats.avg_query_time_ms * (stats.query_count - 1) as f64
                + query_time)
                / stats.query_count as f64;
        }

        tracing::info!(
            "Query completed: {} results in {:.0}ms",
            results.len(),
            start_time.elapsed().as_millis() as f64
        );

        Ok(results)
    }

    /// RAG-specific similarity search with context enrichment
    pub async fn rag_search(
        &self,
        query: &str,
        embedding: &[f32],
        limit: usize,
        context_filter: Option<String>,
    ) -> Result<Vec<RAGSearchResult>> {
        tracing::info!(
            "RAG search for query: '{}' with context: {:?}",
            query,
            context_filter
        );

        let candidates = self.query(embedding, limit * 3, None).await?; // Get more candidates for RAG

        let mut rag_results = Vec::new();

        for record in candidates {
            // Calculate relevance score combining similarity with textual relevance
            let similarity_score = self.cosine_similarity(embedding, &record.embedding);
            let textual_relevance = self.calculate_textual_relevance(query, &record.content);
            let relevance_score = (similarity_score * 0.7) + (textual_relevance * 0.3);

            // Apply context filter if provided
            if let Some(ref context) = context_filter {
                if !self.passes_context_filter(&record, context) {
                    continue;
                }
            }

            let record_id = record.id.clone();
            rag_results.push(RAGSearchResult {
                record,
                similarity_score,
                textual_relevance,
                relevance_score,
                chunk_id: format!("{}_{}", record_id, chrono::Utc::now().timestamp()),
            });
        }

        // Sort by relevance and limit
        rag_results.sort_by(|a, b| {
            b.relevance_score
                .partial_cmp(&a.relevance_score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        rag_results.truncate(limit);

        tracing::info!("RAG search completed: {} results", rag_results.len());
        Ok(rag_results)
    }

    /// Hybrid search combining vector similarity with keyword matching
    pub async fn hybrid_search(
        &self,
        query: &str,
        embedding: &[f32],
        limit: usize,
        keywords: Vec<String>,
    ) -> Result<Vec<HybridSearchResult>> {
        tracing::info!("Hybrid search: text='{}', keywords={:?}", query, keywords);

        let vector_results = self.query(embedding, limit * 2, None).await?;
        let mut hybrid_results = Vec::new();

        for record in vector_results {
            let similarity = self.cosine_similarity(embedding, &record.embedding);
            let keyword_score = self.calculate_keyword_relevance(query, &record.content, &keywords);
            let hybrid_score = (similarity * 0.6) + (keyword_score * 0.4);

            let source_type = if keyword_score > 0.8 {
                "keyword".to_string()
            } else if similarity > 0.8 {
                "vector".to_string()
            } else {
                "hybrid".to_string()
            };

            hybrid_results.push(HybridSearchResult {
                record,
                similarity_score: similarity,
                keyword_score,
                hybrid_score,
                source_type,
            });
        }

        // Sort by hybrid score and limit
        hybrid_results.sort_by(|a, b| {
            b.hybrid_score
                .partial_cmp(&a.hybrid_score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        hybrid_results.truncate(limit);

        Ok(hybrid_results)
    }

    pub async fn create_index(&self, column: &str, index_type: &str) -> Result<()> {
        tracing::info!(
            "Creating LanceDB {} index on column: {}",
            index_type,
            column
        );

        // Simulate index creation time
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

        {
            let mut stats = self.index_stats.write().await;
            stats.index_size_bytes += 1024 * 512; // 512KB for index
        }

        tracing::info!("LanceDB index creation completed");
        Ok(())
    }

    pub async fn optimize(&self) -> Result<()> {
        tracing::info!("Optimizing LanceDB vector storage");

        let start_time = std::time::Instant::now();

        // Simulate optimization operations
        {
            let mut stats = self.index_stats.write().await;
            stats.last_optimized = Some(chrono::Utc::now());

            // Recalculate storage size
            let records = self.records.read().await;
            let mut total_size = 0;
            for record in records.values() {
                total_size += self.calculate_record_size(record);
            }
            stats.storage_size_bytes = total_size as u64;
        }

        // Simulate compaction and reindexing
        tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

        tracing::info!(
            "Optimization completed in {:.0}ms",
            start_time.elapsed().as_millis() as f64
        );
        Ok(())
    }

    pub async fn get_stats(&self) -> Result<StorageStats> {
        let stats = self.index_stats.read().await;

        Ok(StorageStats {
            total_records: stats.total_records,
            storage_size_bytes: stats.storage_size_bytes,
            index_size_bytes: stats.index_size_bytes,
            last_optimized: stats.last_optimized,
        })
    }

    // Helper methods

    fn calculate_record_size(&self, record: &VectorRecord) -> usize {
        // Rough estimation of record size
        record.id.len() +
        record.content.len() +
        (record.embedding.len() * 4) + // f32 = 4 bytes
        record.metadata.values().map(|v| v.len()).sum::<usize>() +
        record.metadata.keys().map(|k| k.len()).sum::<usize>()
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

    fn calculate_textual_relevance(&self, query: &str, content: &str) -> f32 {
        let query_words: std::collections::HashSet<String> =
            query.split_whitespace().map(|w| w.to_lowercase()).collect();

        let content_lower = content.to_lowercase();
        let mut match_count = 0;

        for word in &query_words {
            if content_lower.contains(word.as_str()) {
                match_count += 1;
            }
        }

        if query_words.is_empty() {
            0.0
        } else {
            match_count as f32 / query_words.len() as f32
        }
    }

    fn calculate_keyword_relevance(&self, query: &str, content: &str, keywords: &[String]) -> f32 {
        let content_lower = content.to_lowercase();
        let query_lower = query.to_lowercase();
        let mut score = 0.0;

        // BOOST: Exact match of full query gets significant boost (prioritize precision)
        if content_lower.contains(&query_lower) {
            score += 0.5; // 50% boost for exact query match
            tracing::debug!("Exact match boost applied for query: '{}'", query);
        }

        // Query term relevance
        score += self.calculate_textual_relevance(query, content) * 0.5;

        // Keyword relevance
        for keyword in keywords {
            let keyword_lower = keyword.to_lowercase();
            if content_lower.contains(&keyword_lower) {
                score += 0.1;

                // Extra boost for exact keyword match (not partial)
                if content_lower
                    .split_whitespace()
                    .any(|word| word == keyword_lower)
                {
                    score += 0.05; // Extra 5% for exact word match
                }
            }
        }

        score.min(1.0)
    }

    fn passes_filter(&self, record: &VectorRecord, filter: &HashMap<String, String>) -> bool {
        for (key, value) in filter {
            if let Some(record_value) = record.metadata.get(key) {
                if record_value != value {
                    return false;
                }
            } else {
                return false;
            }
        }
        true
    }

    fn passes_context_filter(&self, record: &VectorRecord, context: &str) -> bool {
        // Simple context filtering - could be enhanced
        record
            .content
            .to_lowercase()
            .contains(&context.to_lowercase())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageStats {
    pub total_records: u64,
    pub storage_size_bytes: u64,
    pub index_size_bytes: u64,
    pub last_optimized: Option<chrono::DateTime<chrono::Utc>>,
}
