///! HTTP client for communicating with Python AI services
///! Uses shared memory and MessagePack for efficient large payload transfer

use anyhow::{Result, Context};
use reqwest::Client;
use serde_json::json;
use std::path::PathBuf;
use tokio::fs;
use tracing::{info, debug};

/// Client for Python embedding service
pub struct EmbeddingClient {
    client: Client,
    base_url: String,
    shared_memory_dir: PathBuf,
}

impl EmbeddingClient {
    /// Create a new embedding client
    pub fn new(base_url: String) -> Result<Self> {
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(300))
            .build()
            .context("Failed to create HTTP client")?;

        let shared_memory_dir = PathBuf::from("/tmp/coderabbit_shm");
        std::fs::create_dir_all(&shared_memory_dir)?;

        Ok(Self {
            client,
            base_url,
            shared_memory_dir,
        })
    }

    /// Generate embeddings for a batch of code snippets
    pub async fn generate_embeddings(&self, code_snippets: Vec<String>) -> Result<Vec<Vec<f32>>> {
        info!("Generating embeddings for {} code snippets", code_snippets.len());

        // Create shared memory path
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_millis();
        let shm_path = self.shared_memory_dir.join(format!("embeddings_{}.msgpack", timestamp));

        // Serialize code snippets to MessagePack
        let data = rmp_serde::to_vec(&code_snippets)
            .context("Failed to serialize code snippets")?;

        // Write to shared memory
        fs::write(&shm_path, &data).await
            .context("Failed to write to shared memory")?;

        debug!("Wrote {} bytes to shared memory: {:?}", data.len(), shm_path);

        // Call Python service
        let url = format!("{}/bridge/embedding_batch", self.base_url);
        let response = self.client
            .post(&url)
            .json(&json!({
                "shared_memory_path": shm_path.to_str().unwrap(),
                "byte_len": data.len()
            }))
            .send()
            .await
            .context("Failed to call embedding service")?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            anyhow::bail!("Embedding service returned error: {}", error_text);
        }

        let response_json: serde_json::Value = response.json().await?;
        let response_path = response_json["response_path"]
            .as_str()
            .context("Missing response_path in response")?;

        // Read embeddings from shared memory response
        let response_data = fs::read(response_path).await
            .context("Failed to read embedding response")?;

        let embeddings: Vec<Vec<f32>> = rmp_serde::from_slice(&response_data)
            .context("Failed to deserialize embeddings")?;

        // Clean up shared memory files
        let _ = fs::remove_file(&shm_path).await;
        let _ = fs::remove_file(response_path).await;

        info!("Generated {} embeddings of dimension {}",
            embeddings.len(),
            embeddings.first().map(|e| e.len()).unwrap_or(0)
        );

        Ok(embeddings)
    }

    /// Generate embedding for a single code snippet
    pub async fn generate_single_embedding(&self, code: String) -> Result<Vec<f32>> {
        let embeddings = self.generate_embeddings(vec![code]).await?;
        embeddings.into_iter().next()
            .context("No embedding returned")
    }
}

/// Client for file analysis service
pub struct AnalysisClient {
    client: Client,
    base_url: String,
    shared_memory_dir: PathBuf,
}

impl AnalysisClient {
    /// Create a new analysis client
    pub fn new(base_url: String) -> Result<Self> {
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(300))
            .build()
            .context("Failed to create HTTP client")?;

        let shared_memory_dir = PathBuf::from("/tmp/coderabbit_shm");
        std::fs::create_dir_all(&shared_memory_dir)?;

        Ok(Self {
            client,
            base_url,
            shared_memory_dir,
        })
    }

    /// Analyze a batch of files
    pub async fn analyze_files(&self, files: Vec<serde_json::Value>) -> Result<serde_json::Value> {
        info!("Analyzing batch of {} files", files.len());

        // Create shared memory path
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_millis();
        let shm_path = self.shared_memory_dir.join(format!("analysis_{}.msgpack", timestamp));

        // Serialize files to MessagePack
        let data = rmp_serde::to_vec(&files)
            .context("Failed to serialize files")?;

        // Write to shared memory
        fs::write(&shm_path, &data).await
            .context("Failed to write to shared memory")?;

        debug!("Wrote {} bytes to shared memory: {:?}", data.len(), shm_path);

        // Call Python service
        let url = format!("{}/bridge/analysis_file_batch", self.base_url);
        let response = self.client
            .post(&url)
            .json(&json!({
                "shared_memory_path": shm_path.to_str().unwrap(),
                "byte_len": data.len()
            }))
            .send()
            .await
            .context("Failed to call analysis service")?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            anyhow::bail!("Analysis service returned error: {}", error_text);
        }

        let response_json = response.json().await?;

        // Clean up shared memory
        let _ = fs::remove_file(&shm_path).await;

        Ok(response_json)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[ignore] // Only run with actual Python service running
    async fn test_embedding_client() {
        let client = EmbeddingClient::new("http://localhost:8081".to_string()).unwrap();

        let code_snippets = vec![
            "def hello_world():\n    print('Hello, World!')".to_string(),
            "fn main() {\n    println!(\"Hello, World!\");\n}".to_string(),
        ];

        let embeddings = client.generate_embeddings(code_snippets).await.unwrap();

        assert_eq!(embeddings.len(), 2);
        assert!(embeddings[0].len() > 0);
        assert!(embeddings[1].len() > 0);
    }

    #[tokio::test]
    #[ignore] // Only run with actual Python service running
    async fn test_analysis_client() {
        let client = AnalysisClient::new("http://localhost:8081".to_string()).unwrap();

        let files = vec![
            json!({
                "path": "test.py",
                "content": "def hello():\n    print('Hello')",
                "language": "python"
            })
        ];

        let result = client.analyze_files(files).await.unwrap();

        assert!(result.get("status").is_some());
    }
}
