//! Python bridge data models - simplified version
//!
//! Simple PyO3 wrappers for data transfer between Rust and Python.

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// Rust-native types for internal use
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonCodeAnalysis {
    pub file_path: String,
    pub language: String,
    pub content: String,
    pub ast_features: PythonASTFeatures,
    pub metrics: PythonCodeMetrics,
    pub issues: Vec<PythonIssue>,
    pub embeddings: Option<Vec<f32>>,
    pub analysis_time_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonASTFeatures {
    pub function_count: u32,
    pub class_count: u32,
    pub import_count: u32,
    pub complexity_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonCodeMetrics {
    pub lines_of_code: u32,
    pub cyclomatic_complexity: u32,
    pub maintainability_index: f32,
    pub technical_debt_minutes: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonIssue {
    pub rule_id: String,
    pub severity: String,
    pub message: String,
    pub line: u32,
    pub column: u32,
    pub fix_suggestion: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonVectorResult {
    pub id: String,
    pub content: String,
    pub similarity_score: f32,
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonAnalysisRequest {
    pub repository_id: String,
    pub pr_number: u32,
    pub files_changed: Vec<String>,
}

/// Simple code analysis result
#[pyclass]
pub struct PyPythonCodeAnalysis {
    file_path: String,
    language: String,
    content: String,
}

#[pymethods]
impl PyPythonCodeAnalysis {
    #[new]
    fn new(file_path: String, language: String, content: String) -> Self {
        Self {
            file_path,
            language,
            content,
        }
    }

    #[getter]
    fn file_path(&self) -> String {
        self.file_path.clone()
    }

    #[getter]
    fn language(&self) -> String {
        self.language.clone()
    }

    #[getter]
    fn content(&self) -> String {
        self.content.clone()
    }
}

/// Simple vector search result
#[pyclass]
pub struct PyPythonVectorResult {
    id: String,
    content: String,
    similarity_score: f32,
}

#[pymethods]
impl PyPythonVectorResult {
    #[new]
    fn new(id: String, content: String, similarity_score: f32) -> Self {
        Self {
            id,
            content,
            similarity_score,
        }
    }

    #[getter]
    fn id(&self) -> String {
        self.id.clone()
    }

    #[getter]
    fn content(&self) -> String {
        self.content.clone()
    }

    #[getter]
    fn similarity_score(&self) -> f32 {
        self.similarity_score
    }
}

/// Simple analysis request
#[pyclass]
pub struct PyPythonAnalysisRequest {
    repository_id: String,
    pr_number: u32,
    files_changed: Vec<String>,
}

#[pymethods]
impl PyPythonAnalysisRequest {
    #[new]
    fn new(repository_id: String, pr_number: u32, files_changed: Vec<String>) -> Self {
        Self {
            repository_id,
            pr_number,
            files_changed,
        }
    }

    #[getter]
    fn repository_id(&self) -> String {
        self.repository_id.clone()
    }

    #[getter]
    fn pr_number(&self) -> u32 {
        self.pr_number
    }

    #[getter]
    fn files_changed(&self) -> Vec<String> {
        self.files_changed.clone()
    }
}
