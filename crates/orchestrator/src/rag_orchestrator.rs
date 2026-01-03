use coderabbit_code_analyzer::{CodeContext, RagAnalysisResult, RagCodeAnalyzer};
/// RAG-enhanced orchestrator for context-aware PR reviews
use coderabbit_shared::{FileChange, Result};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrReviewRequest {
    pub repository_id: String,
    pub pr_number: u64,
    pub files: Vec<FileChange>,
    pub enable_rag: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrReviewResponse {
    pub pr_number: u64,
    pub analyses: Vec<RagAnalysisResult>,
    pub summary: ReviewSummary,
    pub rag_context_used: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewSummary {
    pub total_files: usize,
    pub total_issues: usize,
    pub critical_issues: usize,
    pub high_issues: usize,
    pub medium_issues: usize,
    pub low_issues: usize,
    pub risk_score: f32,
    pub similar_patterns_found: usize,
    pub related_issues_found: usize,
    pub best_practices_applied: usize,
}

pub struct RagOrchestrator {
    rag_analyzer: Arc<RwLock<Option<RagCodeAnalyzer>>>,
    rag_enabled: bool,
}

impl RagOrchestrator {
    pub async fn new(rag_enabled: bool) -> Result<Self> {
        tracing::info!(
            "Initializing RAG orchestrator (RAG enabled: {})",
            rag_enabled
        );

        let rag_analyzer = if rag_enabled {
            match RagCodeAnalyzer::new(true).await {
                Ok(analyzer) => {
                    tracing::info!("RAG analyzer successfully initialized");
                    Some(analyzer)
                }
                Err(e) => {
                    tracing::warn!(
                        "Failed to initialize RAG analyzer: {}. Proceeding without RAG.",
                        e
                    );
                    None
                }
            }
        } else {
            tracing::info!("RAG disabled by configuration");
            None
        };

        let is_analyzer_available = rag_analyzer.is_some();

        Ok(Self {
            rag_analyzer: Arc::new(RwLock::new(rag_analyzer)),
            rag_enabled: rag_enabled && is_analyzer_available,
        })
    }

    /// Review PR with RAG-enhanced context
    pub async fn review_pr(&self, request: PrReviewRequest) -> Result<PrReviewResponse> {
        tracing::info!(
            "Reviewing PR #{} for repository {} ({} files){}",
            request.pr_number,
            request.repository_id,
            request.files.len(),
            if self.rag_enabled { " with RAG" } else { "" }
        );

        // Get analyzer
        let analyzer_guard = self.rag_analyzer.read().await;
        let analyzer = match analyzer_guard.as_ref() {
            Some(a) => a,
            None => {
                tracing::warn!("RAG analyzer not available, falling back to basic analysis");
                return Err(anyhow::anyhow!("RAG analyzer not initialized").into());
            }
        };

        // Perform RAG-enhanced analysis
        let analyses = analyzer
            .analyze_with_context(request.files.clone(), &request.repository_id)
            .await?;

        // Generate summary
        let summary = self.generate_summary(&analyses);

        Ok(PrReviewResponse {
            pr_number: request.pr_number,
            analyses,
            summary,
            rag_context_used: self.rag_enabled,
        })
    }

    fn generate_summary(&self, analyses: &[RagAnalysisResult]) -> ReviewSummary {
        let total_files = analyses.len();
        let mut total_issues = 0;
        let mut critical_issues = 0;
        let mut high_issues = 0;
        let mut medium_issues = 0;
        let mut low_issues = 0;
        let mut total_risk_score = 0.0;
        let mut similar_patterns_found = 0;
        let mut related_issues_found = 0;
        let mut best_practices_applied = 0;

        for analysis in analyses {
            // Count issues by severity
            for issue in &analysis.analysis.issues {
                total_issues += 1;
                match issue.severity.to_lowercase().as_str() {
                    "critical" => critical_issues += 1,
                    "high" => high_issues += 1,
                    "medium" => medium_issues += 1,
                    "low" => low_issues += 1,
                    _ => {}
                }
            }

            // Accumulate risk score
            total_risk_score += analysis.analysis.metrics.cyclomatic_complexity as f32;

            // Count RAG context items
            similar_patterns_found += analysis.context.similar_patterns.len();
            related_issues_found += analysis.context.related_issues.len();
            best_practices_applied += analysis.context.best_practices.len();
        }

        let risk_score = if total_files > 0 {
            total_risk_score / total_files as f32
        } else {
            0.0
        };

        ReviewSummary {
            total_files,
            total_issues,
            critical_issues,
            high_issues,
            medium_issues,
            low_issues,
            risk_score,
            similar_patterns_found,
            related_issues_found,
            best_practices_applied,
        }
    }

    /// Index repository for RAG retrieval
    pub async fn index_repository(
        &self,
        repository_id: String,
        files: Vec<(String, String, String)>, // (file_path, content, language)
    ) -> Result<usize> {
        tracing::info!(
            "Indexing repository {} ({} files)",
            repository_id,
            files.len()
        );

        let analyzer_guard = self.rag_analyzer.read().await;
        let analyzer = match analyzer_guard.as_ref() {
            Some(a) => a,
            None => {
                tracing::warn!("RAG analyzer not available, cannot index repository");
                return Ok(0);
            }
        };

        analyzer.index_codebase(&repository_id, files).await
    }

    /// Prepare review context using RAG
    pub async fn prepare_review_context(
        &self,
        _code_snippet: &str,
        language: &str,
        repository_id: &str,
    ) -> Result<CodeContext> {
        tracing::debug!(
            "Preparing review context for {} code in repo {}",
            language,
            repository_id
        );

        let analyzer_guard = self.rag_analyzer.read().await;
        let analyzer = match analyzer_guard.as_ref() {
            Some(a) => a,
            None => {
                return Ok(CodeContext {
                    similar_patterns: vec![],
                    related_issues: vec![],
                    historical_bugs: vec![],
                    best_practices: vec![],
                });
            }
        };

        // This would extract context via embedding + vector search
        // For now, returning empty context as placeholder
        // In full implementation, this would call analyzer methods
        Ok(CodeContext {
            similar_patterns: vec![],
            related_issues: vec![],
            historical_bugs: vec![],
            best_practices: vec![],
        })
    }

    /// Check if RAG is enabled and operational
    pub fn is_rag_enabled(&self) -> bool {
        self.rag_enabled
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use coderabbit_shared::ChangeType;

    #[tokio::test]
    async fn test_rag_orchestrator_creation() {
        let orchestrator = RagOrchestrator::new(false).await.unwrap();
        assert!(!orchestrator.is_rag_enabled());
    }

    #[tokio::test]
    async fn test_generate_summary_empty() {
        let orchestrator = RagOrchestrator::new(false).await.unwrap();
        let summary = orchestrator.generate_summary(&[]);
        assert_eq!(summary.total_files, 0);
        assert_eq!(summary.total_issues, 0);
    }
}
