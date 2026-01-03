use coderabbit_orchestrator::RagOrchestrator;
/// Codebase indexing service for RAG
///
/// Indexes repositories into vector database for context-aware reviews
use coderabbit_shared::Result;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexingRequest {
    pub repository_id: String,
    pub owner: String,
    pub repo_name: String,
    pub branch: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexingResult {
    pub repository_id: String,
    pub files_indexed: usize,
    pub success: bool,
    pub error: Option<String>,
}

pub struct IndexingService {
    orchestrator: Arc<RwLock<RagOrchestrator>>,
    github_token: String,
    static_context_cache: Option<
        Arc<coderabbit_cache_layer::StaticContextCache<coderabbit_cache_layer::MultiTierCache>>,
    >,
}

impl IndexingService {
    pub fn new(
        orchestrator: Arc<RwLock<RagOrchestrator>>,
        github_token: String,
        static_context_cache: Option<
            Arc<coderabbit_cache_layer::StaticContextCache<coderabbit_cache_layer::MultiTierCache>>,
        >,
    ) -> Self {
        tracing::info!("Indexing service initialized with CAG support");
        Self {
            orchestrator,
            github_token,
            static_context_cache,
        }
    }

    /// Index a repository for RAG
    pub async fn index_repository(&self, request: IndexingRequest) -> Result<IndexingResult> {
        tracing::info!(
            "Indexing repository {}/{} (branch: {})",
            request.owner,
            request.repo_name,
            request.branch
        );

        // Fetch repository files from GitHub
        let files = match self.fetch_repository_files(&request).await {
            Ok(f) => f,
            Err(e) => {
                tracing::error!("Failed to fetch repository files: {}", e);
                return Ok(IndexingResult {
                    repository_id: request.repository_id,
                    files_indexed: 0,
                    success: false,
                    error: Some(format!("Failed to fetch files: {}", e)),
                });
            }
        };

        // Warmup static context cache (CAG layer) for faster PR reviews
        if let Some(cache) = &self.static_context_cache {
            tracing::info!(
                "Warming up static context cache for {}/{}",
                request.owner,
                request.repo_name
            );
            let file_contents: Vec<(String, String)> = files
                .iter()
                .map(|(path, content, _lang)| (path.clone(), content.clone()))
                .collect();

            match cache
                .warmup_repo_cache(&request.owner, &request.repo_name, file_contents)
                .await
            {
                Ok(warmup_result) => {
                    tracing::info!(
                        "Static context cache warmup complete: {} types cached, {} skipped",
                        warmup_result.cached_contexts.len(),
                        warmup_result.skipped_types.len()
                    );
                }
                Err(e) => {
                    tracing::warn!("Static context cache warmup failed (non-critical): {}", e);
                }
            }
        }

        // Index files using RAG orchestrator
        let orchestrator = self.orchestrator.read().await;
        match orchestrator
            .index_repository(request.repository_id.clone(), files)
            .await
        {
            Ok(count) => {
                tracing::info!("Successfully indexed {} files", count);
                Ok(IndexingResult {
                    repository_id: request.repository_id,
                    files_indexed: count,
                    success: true,
                    error: None,
                })
            }
            Err(e) => {
                tracing::error!("Failed to index repository: {}", e);
                Ok(IndexingResult {
                    repository_id: request.repository_id,
                    files_indexed: 0,
                    success: false,
                    error: Some(format!("Indexing failed: {}", e)),
                })
            }
        }
    }

    async fn fetch_repository_files(
        &self,
        request: &IndexingRequest,
    ) -> Result<Vec<(String, String, String)>> {
        tracing::debug!("Fetching files for {}/{}", request.owner, request.repo_name);

        // Use GitHub API to fetch repository tree
        let client = reqwest::Client::new();
        let url = format!(
            "https://api.github.com/repos/{}/{}/git/trees/{}?recursive=1",
            request.owner, request.repo_name, request.branch
        );

        let response = client
            .get(&url)
            .header("Authorization", format!("token {}", self.github_token))
            .header("User-Agent", "CodeRabbit-Indexer")
            .send()
            .await
            .map_err(|e| anyhow::anyhow!("Request failed: {}", e))?;

        if !response.status().is_success() {
            return Err(
                anyhow::anyhow!("GitHub API returned status: {}", response.status()).into(),
            );
        }

        #[derive(Deserialize)]
        struct TreeResponse {
            tree: Vec<TreeItem>,
        }

        #[derive(Deserialize)]
        struct TreeItem {
            path: String,
            #[serde(rename = "type")]
            item_type: String,
            sha: String,
        }

        let tree_response: TreeResponse = response
            .json()
            .await
            .map_err(|e| anyhow::anyhow!("Failed to parse tree response: {}", e))?;

        // Filter to code files AND documentation files
        let code_files: Vec<TreeItem> = tree_response
            .tree
            .into_iter()
            .filter(|item| {
                if item.item_type != "blob" {
                    return false;
                }

                let path_lower = item.path.to_lowercase();

                // Code files
                let is_code = item.path.ends_with(".rs")
                    || item.path.ends_with(".py")
                    || item.path.ends_with(".js")
                    || item.path.ends_with(".ts")
                    || item.path.ends_with(".go")
                    || item.path.ends_with(".java");

                // Documentation files
                let is_doc = item.path.ends_with(".md")
                    || item.path.ends_with(".txt")
                    || item.path.ends_with(".rst")
                    || path_lower.contains("/docs/")
                    || path_lower.contains("/doc/");

                // Critical project files (always index)
                let is_critical = path_lower == "readme.md"
                    || path_lower == "requirements.md"
                    || path_lower == "architecture.md"
                    || path_lower == "todo.md"
                    || path_lower == "tasks.md"
                    || path_lower == "design.md"
                    || path_lower == "contributing.md"
                    || path_lower == "changelog.md"
                    || path_lower.starts_with(".github/")
                    || path_lower.contains("requirement");

                // Config/spec files
                let is_spec = item.path.ends_with(".yaml")
                    || item.path.ends_with(".yml")
                    || item.path.ends_with(".json")
                    || item.path.ends_with(".toml");

                is_code || is_doc || is_critical || is_spec
            })
            .collect();

        tracing::info!("Found {} files to index (code + docs)", code_files.len());

        // Fetch content for each file (limit to prevent rate limiting)
        let max_files = 100; // Limit for now
        let mut files = Vec::new();

        for file in code_files.iter().take(max_files) {
            match self
                .fetch_file_content(&request.owner, &request.repo_name, &file.path)
                .await
            {
                Ok(content) => {
                    let language = self.detect_language(&file.path);
                    files.push((file.path.clone(), content, language));
                }
                Err(e) => {
                    tracing::warn!("Failed to fetch {}: {}", file.path, e);
                    continue;
                }
            }
        }

        Ok(files)
    }

    async fn fetch_file_content(&self, owner: &str, repo: &str, path: &str) -> Result<String> {
        let client = reqwest::Client::new();
        let url = format!(
            "https://api.github.com/repos/{}/{}/contents/{}",
            owner, repo, path
        );

        let response = client
            .get(&url)
            .header("Authorization", format!("token {}", self.github_token))
            .header("User-Agent", "CodeRabbit-Indexer")
            .send()
            .await
            .map_err(|e| anyhow::anyhow!("Request failed: {}", e))?;

        if !response.status().is_success() {
            return Err(anyhow::anyhow!("Failed to fetch file content").into());
        }

        #[derive(Deserialize)]
        struct ContentResponse {
            content: String,
            encoding: String,
        }

        let content_response: ContentResponse = response
            .json()
            .await
            .map_err(|e| anyhow::anyhow!("Failed to parse content response: {}", e))?;

        if content_response.encoding == "base64" {
            let decoded = base64::decode(&content_response.content.replace("\n", ""))
                .map_err(|e| anyhow::anyhow!("Base64 decode failed: {}", e))?;
            Ok(String::from_utf8_lossy(&decoded).to_string())
        } else {
            Ok(content_response.content)
        }
    }

    fn detect_language(&self, file_path: &str) -> String {
        if file_path.ends_with(".rs") {
            "rust".to_string()
        } else if file_path.ends_with(".py") {
            "python".to_string()
        } else if file_path.ends_with(".js") {
            "javascript".to_string()
        } else if file_path.ends_with(".ts") {
            "typescript".to_string()
        } else if file_path.ends_with(".go") {
            "go".to_string()
        } else if file_path.ends_with(".java") {
            "java".to_string()
        } else {
            "unknown".to_string()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_detect_language() {
        let orchestrator = RagOrchestrator::new(false).await.unwrap();
        let service = IndexingService::new(
            Arc::new(RwLock::new(orchestrator)),
            "test".to_string(),
            None,
        );

        assert_eq!(service.detect_language("main.rs"), "rust");
        assert_eq!(service.detect_language("app.py"), "python");
        assert_eq!(service.detect_language("index.js"), "javascript");
        assert_eq!(service.detect_language("component.ts"), "typescript");
    }
}
