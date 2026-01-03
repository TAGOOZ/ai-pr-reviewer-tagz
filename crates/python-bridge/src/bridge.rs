//! Python bridge - real implementation
//!
//! PyO3 bindings for Python integration with CodeRabbit services.
//! Provides synchronous Python API by blocking on async Rust operations.

use crate::services::{
    CodeAnalysisService, CodeAnalysisServiceTrait, VectorService, VectorServiceTrait,
};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::sync::Arc;
use tokio::runtime::Runtime;

/// Python bridge class with real code analysis capabilities
#[pyclass]
pub struct PyPythonBridge {
    runtime: Runtime,
    analysis_service: Arc<CodeAnalysisService>,
    vector_service: Arc<VectorService>,
}

#[pymethods]
impl PyPythonBridge {
    #[new]
    fn new() -> PyResult<Self> {
        // Create tokio runtime for async operations
        let runtime = Runtime::new()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to create runtime: {}", e)))?;

        // Initialize services
        let analysis_service = runtime
            .block_on(async { CodeAnalysisService::new() })
            .map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to create analysis service: {}", e))
            })?;

        let vector_service = runtime
            .block_on(async { VectorService::new().await })
            .map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to create vector service: {}", e))
            })?;

        Ok(Self {
            runtime,
            analysis_service: Arc::new(analysis_service),
            vector_service: Arc::new(vector_service),
        })
    }

    /// Analyze code using real CodeAnalysisService
    fn analyze_code(
        &self,
        file_path: String,
        content: String,
        language: String,
    ) -> PyResult<String> {
        let service = self.analysis_service.clone();

        let result = self
            .runtime
            .block_on(async move { service.analyze_code(&file_path, &content, &language).await });

        match result {
            Ok(analysis) => {
                // Format analysis result as JSON string for Python
                serde_json::to_string(&analysis).map_err(|e| {
                    PyRuntimeError::new_err(format!("Failed to serialize result: {}", e))
                })
            }
            Err(e) => Err(PyRuntimeError::new_err(format!("Analysis failed: {}", e))),
        }
    }

    /// Search for similar code using real VectorService
    fn search_similar_code(&self, query: String, k: usize) -> PyResult<Vec<String>> {
        let vector_service = self.vector_service.clone();
        let analysis_service = self.analysis_service.clone();

        let result = self.runtime.block_on(async move {
            // Generate embedding for the query using CodeAnalysisService
            let embedding = analysis_service.extract_embeddings(&query).await?;

            // Search for similar code using VectorService
            vector_service
                .search_similar_code(&embedding, k, None)
                .await
        });

        match result {
            Ok(results) => {
                // Convert search results to JSON strings
                results
                    .into_iter()
                    .map(|r| {
                        serde_json::to_string(&r).map_err(|e| {
                            PyRuntimeError::new_err(format!("Failed to serialize result: {}", e))
                        })
                    })
                    .collect()
            }
            Err(e) => Err(PyRuntimeError::new_err(format!("Search failed: {}", e))),
        }
    }

    /// Get service statistics
    fn get_stats(&self) -> PyResult<String> {
        Ok(format!(
            "{{\"analysis_service\": \"active\", \"vector_service\": \"active\"}}"
        ))
    }
}
