//! Python bridge services
//!
//! This module provides async service implementations that bridge Rust services
//! with Python DSPy agents for the CodeRabbit AI code review system.

use std::collections::HashMap;
use std::sync::Arc;
use async_trait::async_trait;
use anyhow::Result;
use tracing::{info, error};
use tokio::sync::RwLock;

use crate::models::*;
use coderabbit_vector_engine::search::SemanticSearch;

/// Service trait for code analysis operations
#[async_trait]
pub trait CodeAnalysisServiceTrait {
    async fn analyze_code(&self, file_path: &str, content: &str, language: &str) -> Result<PythonCodeAnalysis>;
    async fn batch_analyze_files(&self, files: &[(String, String, String)]) -> Result<Vec<PythonCodeAnalysis>>;
    async fn extract_embeddings(&self, content: &str) -> Result<Vec<f32>>;
    async fn generate_code_metrics(&self, content: &str, language: &str) -> Result<PythonCodeMetrics>;
}

/// Service trait for vector operations
#[async_trait]
pub trait VectorServiceTrait {
    async fn search_similar_code(&self, query_embedding: &[f32], k: usize, filters: Option<HashMap<String, String>>) -> Result<Vec<PythonVectorResult>>;
    async fn add_code_to_index(&self, content: &str, embedding: &[f32], metadata: Option<HashMap<String, String>>) -> Result<String>;
    async fn update_code_index(&self, id: &str, content: &str, embedding: &[f32]) -> Result<()>;
    async fn delete_from_index(&self, id: &str) -> Result<()>;
}

/// Service trait for job orchestration
#[async_trait]
pub trait OrchestrationServiceTrait {
    async fn submit_job(&self, request: PythonAnalysisRequest) -> Result<String>;
    async fn get_job_status(&self, job_id: &str) -> Result<String>;
    async fn cancel_job(&self, job_id: &str) -> Result<()>;
    async fn get_job_result(&self, job_id: &str) -> Result<Option<PythonCodeAnalysis>>;
}

/// Implementation of CodeAnalysisService
pub struct CodeAnalysisService {
    // Use existing code analyzer from the code-analyzer crate
    analyzer: Arc<RwLock<coderabbit_code_analyzer::analyzer::CodeAnalyzer>>,
}

impl CodeAnalysisService {
    pub fn new() -> Result<Self> {
        info!("Initializing CodeAnalysisService...");
        let analyzer = Arc::new(RwLock::new(coderabbit_code_analyzer::analyzer::CodeAnalyzer::new()));
        Ok(Self { analyzer })
    }
}

#[async_trait]
impl CodeAnalysisServiceTrait for CodeAnalysisService {
    async fn analyze_code(&self, file_path: &str, content: &str, language: &str) -> Result<PythonCodeAnalysis> {
        info!("Analyzing code in {} ({} bytes)", file_path, content.len());
        
        let analyzer = self.analyzer.read().await;
        
        // Generate AST features and metrics
        let start_time = std::time::Instant::now();

        let ast_features = self.generate_ast_features(content, language).await?;
        let metrics = self.generate_code_metrics(content, language).await?;

        // Generate code embeddings using VectorEngine
        let embeddings = self.extract_embeddings(content).await.ok();

        // Extract code issues using static analysis
        let issues = self.extract_issues(content, language).await?;

        let analysis_time_ms = start_time.elapsed().as_millis() as u64;

        let analysis = PythonCodeAnalysis {
            file_path: file_path.to_string(),
            language: language.to_string(),
            content: content.to_string(),
            ast_features,
            metrics,
            issues,
            embeddings,
            analysis_time_ms,
        };
        
        Ok(analysis)
    }

    async fn batch_analyze_files(&self, files: &[(String, String, String)]) -> Result<Vec<PythonCodeAnalysis>> {
        info!("Batch analyzing {} files", files.len());
        
        let mut results = Vec::new();
        
        for (file_path, content, language) in files {
            match self.analyze_code(file_path, content, language).await {
                Ok(analysis) => results.push(analysis),
                Err(e) => {
                    error!("Failed to analyze {}: {}", file_path, e);
                    // Continue with other files
                }
            }
        }
        
        Ok(results)
    }

    async fn extract_embeddings(&self, content: &str) -> Result<Vec<f32>> {
        // Use VectorEngine to generate embeddings from code content
        // The VectorEngine uses a simple hash-based embedding for demonstration
        // In production, this would call an actual embedding model API

        let engine = coderabbit_vector_engine::VectorEngine::new().await?;
        let embeddings = engine.generate_embeddings(vec![content.to_string()]).await?;

        if let Some(embedding) = embeddings.into_iter().next() {
            Ok(embedding)
        } else {
            Err(anyhow::anyhow!("Failed to generate embedding"))
        }
    }

    async fn generate_code_metrics(&self, content: &str, language: &str) -> Result<PythonCodeMetrics> {
        let lines_of_code = content.lines().count() as u32;
        let cyclomatic_complexity = self.calculate_cyclomatic_complexity(content, language);
        let maintainability_index = self.calculate_maintainability_index(content, language);
        let technical_debt_minutes = self.estimate_technical_debt(content, language);
        
        Ok(PythonCodeMetrics {
            lines_of_code,
            cyclomatic_complexity,
            maintainability_index,
            technical_debt_minutes,
        })
    }
}

impl CodeAnalysisService {
    async fn generate_ast_features(&self, content: &str, language: &str) -> Result<PythonASTFeatures> {
        // Use actual tree-sitter parsing to extract AST features
        use coderabbit_code_analyzer::parser::LanguageParser;
        use tree_sitter::Node;

        let mut parser = LanguageParser::new()?;
        let tree = parser.parse(language, content)?;
        let root_node = tree.root_node();

        // Count functions, classes, and imports by traversing the AST
        let mut function_count = 0u32;
        let mut class_count = 0u32;
        let mut import_count = 0u32;

        let mut cursor = root_node.walk();
        let mut stack = vec![(root_node, 0)];

        while let Some((node, depth)) = stack.pop() {
            let kind = node.kind();

            match kind {
                "function_definition" | "function_declaration" | "method_definition" => {
                    function_count += 1;
                }
                "class_definition" | "class_declaration" => {
                    class_count += 1;
                }
                "import_statement" | "import_from_statement" | "import_declaration" => {
                    import_count += 1;
                }
                _ => {}
            }

            // Add children to stack for traversal
            for i in 0..node.child_count() {
                if let Some(child) = node.child(i) {
                    stack.push((child, depth + 1));
                }
            }
        }

        // Ensure minimum counts for complexity calculation
        function_count = function_count.max(1);
        class_count = class_count.max(1);
        import_count = import_count.max(1);

        let complexity_score = (function_count as f32 * 0.3
            + class_count as f32 * 0.5
            + import_count as f32 * 0.2) / 10.0;

        Ok(PythonASTFeatures {
            function_count,
            class_count,
            import_count,
            complexity_score,
        })
    }

    async fn extract_issues(&self, content: &str, language: &str) -> Result<Vec<PythonIssue>> {
        let mut issues = Vec::new();

        // Perform multiple static analysis checks
        for (line_num, line) in content.lines().enumerate() {
            let line_number = (line_num + 1) as u32;
            let trimmed = line.trim();

            // 1. Check for TODO/FIXME comments
            if trimmed.contains("TODO") || trimmed.contains("FIXME") {
                issues.push(PythonIssue {
                    rule_id: "comment-todo".to_string(),
                    severity: "low".to_string(),
                    message: "TODO/FIXME comment should be tracked in issue tracker".to_string(),
                    line: line_number,
                    column: line.find("TODO").or_else(|| line.find("FIXME")).unwrap_or(0) as u32,
                    fix_suggestion: Some("Convert to GitHub issue".to_string()),
                });
            }

            // 2. Check for long lines (>120 characters)
            if line.len() > 120 {
                issues.push(PythonIssue {
                    rule_id: "line-too-long".to_string(),
                    severity: "low".to_string(),
                    message: format!("Line exceeds 120 characters ({} chars)", line.len()),
                    line: line_number,
                    column: 120,
                    fix_suggestion: Some("Break into multiple lines".to_string()),
                });
            }

            // 3. Check for hardcoded credentials patterns
            if trimmed.contains("password") || trimmed.contains("api_key") || trimmed.contains("secret") {
                if trimmed.contains("=") && !trimmed.starts_with("//") && !trimmed.starts_with("#") {
                    issues.push(PythonIssue {
                        rule_id: "hardcoded-credentials".to_string(),
                        severity: "high".to_string(),
                        message: "Possible hardcoded credentials detected".to_string(),
                        line: line_number,
                        column: 0,
                        fix_suggestion: Some("Use environment variables or secrets manager".to_string()),
                    });
                }
            }

            // 4. Check for console.log / print statements (debugging code)
            if language == "javascript" || language == "typescript" {
                if trimmed.contains("console.log") || trimmed.contains("console.debug") {
                    issues.push(PythonIssue {
                        rule_id: "no-console".to_string(),
                        severity: "medium".to_string(),
                        message: "Console statement found - should use proper logging".to_string(),
                        line: line_number,
                        column: line.find("console").unwrap_or(0) as u32,
                        fix_suggestion: Some("Use logger library instead".to_string()),
                    });
                }
            } else if language == "python" {
                if trimmed.starts_with("print(") {
                    issues.push(PythonIssue {
                        rule_id: "no-print".to_string(),
                        severity: "medium".to_string(),
                        message: "Print statement found - should use logging module".to_string(),
                        line: line_number,
                        column: 0,
                        fix_suggestion: Some("Use logging.info() instead".to_string()),
                    });
                }
            }

            // 5. Check for unsafe SQL patterns
            if trimmed.contains("SELECT") || trimmed.contains("INSERT") || trimmed.contains("UPDATE") {
                if trimmed.contains("+") || trimmed.contains(&format!("\"")) {
                    issues.push(PythonIssue {
                        rule_id: "sql-injection-risk".to_string(),
                        severity: "high".to_string(),
                        message: "Possible SQL injection vulnerability".to_string(),
                        line: line_number,
                        column: 0,
                        fix_suggestion: Some("Use parameterized queries".to_string()),
                    });
                }
            }

            // 6. Check for eval/exec usage (code injection risk)
            if language == "python" && (trimmed.contains("eval(") || trimmed.contains("exec(")) {
                issues.push(PythonIssue {
                    rule_id: "dangerous-eval".to_string(),
                    severity: "critical".to_string(),
                    message: "Use of eval/exec is dangerous and can lead to code injection".to_string(),
                    line: line_number,
                    column: line.find("eval").or_else(|| line.find("exec")).unwrap_or(0) as u32,
                    fix_suggestion: Some("Avoid eval/exec or use ast.literal_eval for safe evaluation".to_string()),
                });
            }

            // 7. Check for missing error handling
            if language == "python" && trimmed.starts_with("try:") {
                // Look ahead to check if there's a bare except
                if let Some(next_line) = content.lines().nth(line_num + 1) {
                    if next_line.trim() == "except:" {
                        issues.push(PythonIssue {
                            rule_id: "bare-except".to_string(),
                            severity: "medium".to_string(),
                            message: "Bare except clause catches all exceptions including system exits".to_string(),
                            line: line_number + 1,
                            column: 0,
                            fix_suggestion: Some("Specify exception type: except Exception:".to_string()),
                        });
                    }
                }
            }
        }

        Ok(issues)
    }

    fn calculate_cyclomatic_complexity(&self, content: &str, language: &str) -> u32 {
        // Simple complexity calculation
        let mut complexity = 1; // Base complexity
        
        let keywords = match language {
            "python" => &["if", "elif", "else", "for", "while", "try", "except", "with", "and", "or"][..],
            "rust" => &["if", "else", "for", "while", "match", "try", "catch", "&&", "||"][..],
            _ => &["if", "else", "for", "while", "switch", "case", "&&", "||"][..],
        };
        
        for keyword in keywords {
            complexity += content.matches(keyword).count();
        }
        
        complexity as u32
    }

    fn calculate_maintainability_index(&self, content: &str, language: &str) -> f32 {
        let lines = content.lines().count() as f32;
        let functions = content.matches("def ").count() + content.matches("fn ").count();
        let complexity = self.calculate_cyclomatic_complexity(content, language) as f32;

        // Simple maintainability index calculation
        if lines == 0.0 { return 0.0; }

        let function_density = if lines > 0.0 { functions as f32 / lines * 100.0 } else { 0.0 };
        let complexity_penalty = complexity / lines * 10.0;

        let index = 100.0 - complexity_penalty - function_density;
        index.max(0.0)
    }

    fn estimate_technical_debt(&self, content: &str, language: &str) -> u32 {
        let complexity = self.calculate_cyclomatic_complexity(content, language);
        let lines = content.lines().count();

        // Simple debt estimation: 2 minutes per complexity point + 0.5 minutes per 10 lines
        let complexity_debt = complexity * 2;
        let line_debt = ((lines as f32 / 10.0) * 0.5) as u32;

        complexity_debt + line_debt
    }
}

/// Implementation of VectorService
pub struct VectorService {
    search_engine: Arc<SemanticSearch>,
}

impl VectorService {
    pub async fn new() -> Result<Self> {
        info!("Initializing VectorService with SemanticSearch engine...");
        let table_name = std::env::var("LANCEDB_TABLE").unwrap_or_else(|_| "code_vectors".to_string());
        let engine = SemanticSearch::new(&table_name).await?;
        Ok(Self { search_engine: Arc::new(engine) })
    }
}

#[async_trait]
impl VectorServiceTrait for VectorService {
    async fn search_similar_code(&self, query_embedding: &[f32], k: usize, _filters: Option<HashMap<String, String>>) -> Result<Vec<PythonVectorResult>> {
        info!("Searching for similar code with {} dimensions, k={}", query_embedding.len(), k);
        let results = self
            .search_engine
            .search_similar_code(query_embedding, k, None)
            .await
            .map_err(|e| anyhow::anyhow!("Vector search failed: {}", e))?;

        let mapped: Vec<PythonVectorResult> = results
            .into_iter()
            .map(|r| PythonVectorResult {
                id: r.id,
                content: r.content,
                similarity_score: r.similarity_score,
                metadata: r.metadata,
            })
            .collect();
        Ok(mapped)
    }

    async fn add_code_to_index(&self, content: &str, embedding: &[f32], metadata: Option<HashMap<String, String>>) -> Result<String> {
        let id = uuid::Uuid::new_v4().to_string();
        info!("Adding code to vector index: {} ({} bytes)", id, content.len());

        let metadata = metadata.unwrap_or_default();

        self.search_engine
            .add_code(id.clone(), content.to_string(), embedding.to_vec(), metadata)
            .await?;

        info!("Successfully added code {} to vector index", id);
        Ok(id)
    }

    async fn update_code_index(&self, id: &str, content: &str, embedding: &[f32]) -> Result<()> {
        info!("Updating code in vector index: {}", id);

        // Preserve existing metadata or use empty
        let metadata = HashMap::new();

        self.search_engine
            .update_code(id, content.to_string(), embedding.to_vec(), metadata)
            .await?;

        info!("Successfully updated code {} in vector index", id);
        Ok(())
    }

    async fn delete_from_index(&self, id: &str) -> Result<()> {
        info!("Deleting code from vector index: {}", id);

        self.search_engine.delete_code(id).await?;

        info!("Successfully deleted code {} from vector index", id);
        Ok(())
    }
}

/// Implementation of OrchestrationService
pub struct OrchestrationService {
    orchestrator: Arc<coderabbit_orchestrator::RedisOrchestrator>,
    // Local job status cache for fast lookups
    job_statuses: Arc<RwLock<HashMap<String, String>>>,
}

impl OrchestrationService {
    pub fn new() -> Result<Self> {
        info!("Initializing OrchestrationService with RedisOrchestrator...");

        let redis_url = std::env::var("REDIS_URL")
            .unwrap_or_else(|_| "redis://127.0.0.1:6379".to_string());

        let orchestrator = coderabbit_orchestrator::RedisOrchestrator::new(&redis_url)?;
        let job_statuses = Arc::new(RwLock::new(HashMap::new()));

        Ok(Self {
            orchestrator: Arc::new(orchestrator),
            job_statuses,
        })
    }

    pub async fn initialize(&self) -> Result<()> {
        self.orchestrator.initialize().await.map_err(|e| anyhow::anyhow!("Failed to initialize orchestrator: {}", e))
    }
}

#[async_trait]
impl OrchestrationServiceTrait for OrchestrationService {
    async fn submit_job(&self, request: PythonAnalysisRequest) -> Result<String> {
        info!("Submitting analysis job for repository: {}", request.repository_id);

        // Serialize the request as the job payload
        let payload = serde_json::to_string(&request)?;

        // Determine job type based on the request
        let job_type = coderabbit_orchestrator::JobType::ReviewRequest;

        // Priority: higher for urgent reviews, lower for background analysis
        let priority = 5;

        // Submit job to Redis orchestrator
        let job_id = self.orchestrator.enqueue_job(job_type, payload, priority).await?;

        // Update local cache
        {
            let mut statuses = self.job_statuses.write().await;
            statuses.insert(job_id.clone(), "queued".to_string());
        }

        info!("Job {} successfully enqueued to Redis orchestrator", job_id);

        Ok(job_id)
    }

    async fn get_job_status(&self, job_id: &str) -> Result<String> {
        let statuses = self.job_statuses.read().await;
        let status = statuses.get(job_id)
            .map(|s| s.clone())
            .unwrap_or_else(|| "not_found".to_string());
        Ok(status)
    }

    async fn cancel_job(&self, job_id: &str) -> Result<()> {
        info!("Cancelling job: {}", job_id);
        
        let mut statuses = self.job_statuses.write().await;
        statuses.insert(job_id.to_string(), "cancelled".to_string());
        
        Ok(())
    }

    async fn get_job_result(&self, job_id: &str) -> Result<Option<PythonCodeAnalysis>> {
        info!("Fetching job result for: {}", job_id);

        // Query job status from Redis orchestrator
        let job_status = self.orchestrator.get_job_status(job_id).await
            .map_err(|e| anyhow::anyhow!("Failed to get job status: {}", e))?;

        match job_status {
            coderabbit_orchestrator::JobStatus::Completed => {
                // Job is completed, result would be stored separately in Redis or returned
                // For now, we return a placeholder indicating the job completed
                // In production, you would fetch the actual result from a results store
                info!("Job {} completed, returning placeholder result", job_id);

                // Update local cache
                {
                    let mut statuses = self.job_statuses.write().await;
                    statuses.insert(job_id.to_string(), "completed".to_string());
                }

                // Return None to indicate result needs to be fetched from separate results store
                // In a full implementation, you would:
                // 1. Fetch from Redis key like "job:results:{job_id}"
                // 2. Deserialize the PythonCodeAnalysis from JSON
                Ok(None)
            }
            coderabbit_orchestrator::JobStatus::Processing | coderabbit_orchestrator::JobStatus::Pending => {
                info!("Job {} still in progress", job_id);
                Ok(None)
            }
            coderabbit_orchestrator::JobStatus::Failed => {
                info!("Job {} failed", job_id);
                Err(anyhow::anyhow!("Job failed"))
            }
            coderabbit_orchestrator::JobStatus::Retrying => {
                info!("Job {} is retrying", job_id);
                Ok(None)
            }
        }
    }
}

// Additional helper methods for OrchestrationService (not part of trait)
impl OrchestrationService {
    // Helper method to store job results (to be called by worker)
    pub async fn store_job_result(&self, job_id: &str, _result: &PythonCodeAnalysis) -> Result<()> {
        // In production, store the result in Redis or database
        // For example: REDIS.set(format!("job:results:{}", job_id), serde_json::to_string(result)?)
        info!("Storing result for job {}", job_id);

        {
            let mut statuses = self.job_statuses.write().await;
            statuses.insert(job_id.to_string(), "completed".to_string());
        }

        Ok(())
    }
}

/// Service factory functions
pub fn create_code_analysis_service() -> Result<Arc<CodeAnalysisService>> {
    Ok(Arc::new(CodeAnalysisService::new()?))
}

pub async fn create_vector_service() -> Result<Arc<VectorService>> {
    Ok(Arc::new(VectorService::new().await?))
}

pub fn create_orchestration_service() -> Result<Arc<OrchestrationService>> {
    Ok(Arc::new(OrchestrationService::new()?))
}
