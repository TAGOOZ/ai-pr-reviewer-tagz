//! CodeRabbit Python Bridge - Working Version
//!
//! Simple PyO3 bindings for Python integration with CodeRabbit services.

pub mod bridge;
pub mod client;
pub mod models;
pub mod services;

use pyo3::prelude::*;

#[pymodule]
fn coderabbit_python_bridge(_py: Python, m: &PyModule) -> PyResult<()> {
    // Add main bridge class to Python module
    m.add_class::<bridge::PyPythonBridge>()?;

    // Add data models
    m.add_class::<models::PyPythonCodeAnalysis>()?;
    m.add_class::<models::PyPythonVectorResult>()?;
    m.add_class::<models::PyPythonAnalysisRequest>()?;

    Ok(())
}
