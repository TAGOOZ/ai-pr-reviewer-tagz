/// RAG-enhanced code analyzer that retrieves similar code context
/// for better PR reviews

use coderabbit_shared::{Result, FileChange};
use coderabbit_vector_engine::{VectorEngine, SearchResult};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::analyzer::{CodeAnalyzer, CodeAnalysisResult};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeContext {
    pub similar_patterns: Vec<SimilarCode>,
    pub related_issues: Vec<RelatedIssue>,
    pub historical_bugs: Vec<HistoricalBug>,
    pub best_practices: Vec<BestPractice>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimilarCode {
    pub file_path: String,
    pub content: String,
    pub similarity_score: f32,
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelatedIssue {
    pub issue_id: String,
    pub title: String,
    pub description: String,
    pub similarity_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoricalBug {
    pub bug_id: String,
    pub description: String,
    pub fix_commit: String,
    pub similarity_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BestPractice {
    pub practice_id: String,
    pub description: String,
    pub category: String,
    pub relevance_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RagAnalysisResult {
    pub analysis: CodeAnalysisResult,
    pub context: CodeContext,
    pub rag_enhanced: bool,
}

pub struct RagCodeAnalyzer {
    base_analyzer: CodeAnalyzer,
    vector_engine: Option<VectorEngine>,
    rag_enabled: bool,
}

impl RagCodeAnalyzer {
    pub async fn new(rag_enabled: bool) -> Result<Self> {
        let base_analyzer = CodeAnalyzer::new();

        let vector_engine = if rag_enabled {
            match VectorEngine::new().await {
                Ok(engine) => {
                    tracing::info!("RAG-enhanced analyzer initialized with vector engine");
                    Some(engine)
                }
                Err(e) => {
                    tracing::warn!("Failed to initialize vector engine: {}. RAG features disabled.", e);
                    None
                }
            }
        } else {
            tracing::info!("RAG features disabled");
            None
        };

        let is_engine_available = vector_engine.is_some();

        Ok(Self {
            base_analyzer,
            vector_engine,
            rag_enabled: rag_enabled && is_engine_available,
        })
    }

    /// Analyze files with RAG context enhancement
    pub async fn analyze_with_context(
        &self,
        files: Vec<FileChange>,
        repository_id: &str,
    ) -> Result<Vec<RagAnalysisResult>> {
        tracing::info!(
            "Analyzing {} files{} for repository: {}",
            files.len(),
            if self.rag_enabled { " with RAG context" } else { "" },
            repository_id
        );

        let mut results = Vec::new();

        for file in files {
            let result = self.analyze_single_file_with_context(file, repository_id).await?;
            results.push(result);
        }

        Ok(results)
    }

    async fn analyze_single_file_with_context(
        &self,
        file: FileChange,
        repository_id: &str,
    ) -> Result<RagAnalysisResult> {
        // Perform base code analysis
        let analysis = self.base_analyzer.analyze_files(vec![file.clone()]).await?
            .into_iter()
            .next()
            .unwrap();

        // If RAG is disabled or no vector engine, return without context
        if !self.rag_enabled || self.vector_engine.is_none() {
            return Ok(RagAnalysisResult {
                analysis,
                context: CodeContext {
                    similar_patterns: vec![],
                    related_issues: vec![],
                    historical_bugs: vec![],
                    best_practices: vec![],
                },
                rag_enhanced: false,
            });
        }

        // Generate embedding for the code
        let embedding = match self.base_analyzer.extract_embeddings(&file.content).await {
            Ok(emb) if !emb.is_empty() => emb,
            Ok(_) => {
                tracing::warn!("Empty embedding returned for file: {}", file.path);
                return Ok(RagAnalysisResult {
                    analysis,
                    context: CodeContext {
                        similar_patterns: vec![],
                        related_issues: vec![],
                        historical_bugs: vec![],
                        best_practices: vec![],
                    },
                    rag_enhanced: false,
                });
            }
            Err(e) => {
                tracing::error!("Failed to generate embedding: {}", e);
                return Ok(RagAnalysisResult {
                    analysis,
                    context: CodeContext {
                        similar_patterns: vec![],
                        related_issues: vec![],
                        historical_bugs: vec![],
                        best_practices: vec![],
                    },
                    rag_enhanced: false,
                });
            }
        };

        // Retrieve context from vector database
        let context = self.retrieve_context(&embedding, &file.language, repository_id).await?;

        Ok(RagAnalysisResult {
            analysis,
            context,
            rag_enhanced: true,
        })
    }

    async fn retrieve_context(
        &self,
        embedding: &[f32],
        language: &str,
        repository_id: &str,
    ) -> Result<CodeContext> {
        let engine = self.vector_engine.as_ref().unwrap();

        tracing::debug!("Retrieving RAG context for language: {}, repo: {}", language, repository_id);

        // Search for similar code patterns (top 5)
        let similar_patterns = match engine.search_code_context("", language, 5).await {
            Ok(results) => self.convert_to_similar_code(results),
            Err(e) => {
                tracing::warn!("Failed to retrieve similar patterns: {}", e);
                vec![]
            }
        };

        // Search for related issues (top 3)
        let related_issues = match self.search_related_issues(embedding, repository_id).await {
            Ok(issues) => issues,
            Err(e) => {
                tracing::warn!("Failed to retrieve related issues: {}", e);
                vec![]
            }
        };

        // Search for historical bugs (top 3)
        let historical_bugs = match self.search_historical_bugs(embedding, repository_id).await {
            Ok(bugs) => bugs,
            Err(e) => {
                tracing::warn!("Failed to retrieve historical bugs: {}", e);
                vec![]
            }
        };

        // Get best practices for this language
        let best_practices = self.get_best_practices(language, embedding).await?;

        Ok(CodeContext {
            similar_patterns,
            related_issues,
            historical_bugs,
            best_practices,
        })
    }

    fn convert_to_similar_code(&self, search_results: Vec<SearchResult>) -> Vec<SimilarCode> {
        search_results
            .into_iter()
            .map(|result| SimilarCode {
                file_path: result.file_path.unwrap_or_else(|| "unknown".to_string()),
                content: result.content,
                similarity_score: result.similarity_score,
                metadata: result.metadata,
            })
            .collect()
    }

    async fn search_related_issues(
        &self,
        embedding: &[f32],
        repository_id: &str,
    ) -> Result<Vec<RelatedIssue>> {
        let engine = self.vector_engine.as_ref().unwrap();

        // Add metadata filter for issues
        let mut filters = HashMap::new();
        filters.insert("repository_id".to_string(), repository_id.to_string());
        filters.insert("type".to_string(), "issue".to_string());

        let results = engine.similarity_search(embedding, 3).await?;

        Ok(results
            .into_iter()
            .map(|result| RelatedIssue {
                issue_id: result.id,
                title: result.metadata.get("title").cloned().unwrap_or_default(),
                description: result.content,
                similarity_score: result.similarity_score,
            })
            .collect())
    }

    async fn search_historical_bugs(
        &self,
        embedding: &[f32],
        repository_id: &str,
    ) -> Result<Vec<HistoricalBug>> {
        let engine = self.vector_engine.as_ref().unwrap();

        // Add metadata filter for bugs
        let mut filters = HashMap::new();
        filters.insert("repository_id".to_string(), repository_id.to_string());
        filters.insert("type".to_string(), "bug".to_string());

        let results = engine.similarity_search(embedding, 3).await?;

        Ok(results
            .into_iter()
            .map(|result| HistoricalBug {
                bug_id: result.id.clone(),
                description: result.content,
                fix_commit: result.metadata.get("fix_commit").cloned().unwrap_or_default(),
                similarity_score: result.similarity_score,
            })
            .collect())
    }

    async fn get_best_practices(
        &self,
        language: &str,
        embedding: &[f32],
    ) -> Result<Vec<BestPractice>> {
        let engine = self.vector_engine.as_ref().unwrap();

        // Add metadata filter for best practices
        let mut filters = HashMap::new();
        filters.insert("language".to_string(), language.to_string());
        filters.insert("type".to_string(), "best_practice".to_string());

        let results = engine.similarity_search(embedding, 3).await?;

        Ok(results
            .into_iter()
            .map(|result| BestPractice {
                practice_id: result.id,
                description: result.content,
                category: result.metadata.get("category").cloned().unwrap_or_else(|| "general".to_string()),
                relevance_score: result.similarity_score,
            })
            .collect())
    }

    /// Index codebase for RAG retrieval
    pub async fn index_codebase(
        &self,
        repository_id: &str,
        files: Vec<(String, String, String)>, // (file_path, content, language)
    ) -> Result<usize> {
        if !self.rag_enabled || self.vector_engine.is_none() {
            tracing::warn!("RAG not enabled, skipping indexing");
            return Ok(0);
        }

        let engine = self.vector_engine.as_ref().unwrap();

        tracing::info!("Indexing {} files for repository: {}", files.len(), repository_id);

        // Generate embeddings for all files
        let contents: Vec<String> = files.iter().map(|(_, content, _)| content.clone()).collect();
        let embeddings = engine.generate_embeddings(contents.clone()).await?;

        // Prepare records for batch insertion
        let mut records = Vec::new();
        let mut contents_for_insert = Vec::new();

        for (i, (file_path, content, language)) in files.into_iter().enumerate() {
            if i >= embeddings.len() {
                tracing::warn!("Embedding mismatch at index {}", i);
                break;
            }

            let mut metadata = HashMap::new();
            metadata.insert("repository_id".to_string(), repository_id.to_string());
            metadata.insert("file_path".to_string(), file_path.clone());
            metadata.insert("language".to_string(), language);
            metadata.insert("type".to_string(), "code".to_string());

            let id = format!("{}:{}", repository_id, file_path);
            records.push((id, embeddings[i].clone(), metadata));
            contents_for_insert.push(content);
        }

        // Batch insert into vector database
        engine.batch_insert(records, contents_for_insert).await?;

        tracing::info!("Successfully indexed codebase");
        Ok(embeddings.len())
    }

    /// Check if RAG is enabled
    pub fn is_rag_enabled(&self) -> bool {
        self.rag_enabled
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use coderabbit_shared::ChangeType;

    #[tokio::test]
    async fn test_rag_analyzer_creation_disabled() {
        let analyzer = RagCodeAnalyzer::new(false).await.unwrap();
        assert!(!analyzer.is_rag_enabled());
    }

    #[tokio::test]
    async fn test_analyze_without_rag() {
        let analyzer = RagCodeAnalyzer::new(false).await.unwrap();

        let files = vec![FileChange {
            path: "test.rs".to_string(),
            change_type: ChangeType::Modified,
            content: "fn main() {}".to_string(),
            diff: "".to_string(),
            language: "rust".to_string(),
        }];

        let results = analyzer.analyze_with_context(files, "test-repo").await.unwrap();
        assert_eq!(results.len(), 1);
        assert!(!results[0].rag_enhanced);
    }
}
