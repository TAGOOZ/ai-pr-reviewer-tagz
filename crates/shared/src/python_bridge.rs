use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use crossbeam_channel::{Receiver, Sender};
use memmap2::MmapMut;
use crate::models::{CodeAnalysisRequest, CodeAnalysisResult, FileChange};
use crate::error::{CodeRabbitError, Result};

#[derive(Debug, Clone)]
pub struct SharedMemoryRegion {
    pub id: String,
    pub size: usize,
    pub data: Arc<Mutex<MmapMut>>,
}

#[derive(Debug, Clone)]
pub struct PythonBridge {
    message_sender: Sender<PythonMessage>,
    message_receiver: Receiver<PythonResponse>,
    shared_memory: Arc<Mutex<HashMap<String, SharedMemoryRegion>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonMessage {
    pub id: String,
    pub message_type: String,
    pub payload: Vec<u8>,
    pub shared_memory_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonResponse {
    pub id: String,
    pub success: bool,
    pub payload: Vec<u8>,
    pub error: Option<String>,
}

impl PythonBridge {
    pub fn new() -> Result<Self, CodeRabbitError> {
        let (msg_tx, msg_rx) = crossbeam_channel::unbounded();
        let (resp_tx, resp_rx) = crossbeam_channel::unbounded();
        
        Ok(Self {
            message_sender: msg_tx,
            message_receiver: resp_rx,
            shared_memory: Arc::new(Mutex::new(HashMap::new())),
        })
    }

    pub async fn send_analysis_request(
        &self,
        request: &CodeAnalysisRequest,
    ) -> Result<String, CodeRabbitError> {
        let payload = rmp_serde::to_vec(request)
            .map_err(|e| CodeRabbitError::SerializationError(e.to_string()))?;

        let message = PythonMessage {
            id: uuid::Uuid::new_v4().to_string(),
            message_type: "analysis_request".to_string(),
            payload,
            shared_memory_id: None,
        };

        self.message_sender
            .send(message.clone())
            .map_err(|e| CodeRabbitError::CommunicationError(e.to_string()))?;

        Ok(message.id)
    }

    pub async fn send_large_payload(
        &self,
        data: &[u8],
    ) -> Result<String, CodeRabbitError> {
        let memory_id = uuid::Uuid::new_v4().to_string();
        
        let mut mmap = MmapMut::map_anon(data.len())
            .map_err(|e| CodeRabbitError::MemoryError(e.to_string()))?;
        
        mmap[..data.len()].copy_from_slice(data);
        
        let region = SharedMemoryRegion {
            id: memory_id.clone(),
            size: data.len(),
            data: Arc::new(Mutex::new(mmap)),
        };

        let mut shared_memory = self.shared_memory.lock().await;
        shared_memory.insert(memory_id.clone(), region);

        Ok(memory_id)
    }

    pub async fn send_file_batch_via_shared_memory(
        &self,
        files: &[FileChange],
    ) -> Result<String, CodeRabbitError> {
        // Serialize using MessagePack (compact, fast)
        let payload = rmp_serde::to_vec(files)
            .map_err(|e| CodeRabbitError::SerializationError(e.to_string()))?;

        // Write to shared memory and get an ID
        let shared_memory_id = self.send_large_payload(&payload).await?;

        // Send a lightweight control message referencing shared memory
        let message = PythonMessage {
            id: uuid::Uuid::new_v4().to_string(),
            message_type: "analysis_file_batch".to_string(),
            payload: Vec::new(),
            shared_memory_id: Some(shared_memory_id.clone()),
        };

        self.message_sender
            .send(message)
            .map_err(|e| CodeRabbitError::CommunicationError(e.to_string()))?;

        Ok(shared_memory_id)
    }

    pub async fn send_embeddings_batch_via_shared_memory(
        &self,
        code_snippets: &[String],
    ) -> Result<String, CodeRabbitError> {
        let payload = rmp_serde::to_vec(code_snippets)
            .map_err(|e| CodeRabbitError::SerializationError(e.to_string()))?;

        let shared_memory_id = self.send_large_payload(&payload).await?;

        let message = PythonMessage {
            id: uuid::Uuid::new_v4().to_string(),
            message_type: "embedding_batch".to_string(),
            payload: Vec::new(),
            shared_memory_id: Some(shared_memory_id.clone()),
        };

        self.message_sender
            .send(message)
            .map_err(|e| CodeRabbitError::CommunicationError(e.to_string()))?;

        Ok(shared_memory_id)
    }
}

#[pymodule]
fn coderabbit_bridge(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyCodeAnalysisRequest>()?;
    m.add_function(wrap_pyfunction!(process_analysis_request, m)?)?;
    Ok(())
}

#[pyclass]
struct PyCodeAnalysisRequest {
    #[pyo3(get, set)]
    repository_id: String,
    #[pyo3(get, set)]
    pr_number: i32,
    #[pyo3(get, set)]
    files_changed: Vec<String>,
}

#[pyfunction]
fn process_analysis_request(
    _py: Python,
    request: &PyCodeAnalysisRequest,
) -> PyResult<String> {
    Ok(uuid::Uuid::new_v4().to_string())
}
