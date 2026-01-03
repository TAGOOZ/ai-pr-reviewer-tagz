//! Graceful shutdown handling
//!
//! Handles SIGTERM/SIGINT for clean shutdown.

use std::time::Duration;
use tokio::signal;
use tokio::sync::broadcast;

/// Default shutdown timeout
pub const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(30);

/// Shutdown signal receiver
pub type ShutdownReceiver = broadcast::Receiver<()>;

/// Shutdown controller
pub struct ShutdownController {
    sender: broadcast::Sender<()>,
}

impl ShutdownController {
    pub fn new() -> (Self, ShutdownReceiver) {
        let (sender, receiver) = broadcast::channel(1);
        (Self { sender }, receiver)
    }

    /// Trigger shutdown
    pub fn shutdown(&self) {
        let _ = self.sender.send(());
    }

    /// Get a new receiver
    pub fn subscribe(&self) -> ShutdownReceiver {
        self.sender.subscribe()
    }
}

impl Default for ShutdownController {
    fn default() -> Self {
        Self::new().0
    }
}

/// Wait for shutdown signal (SIGTERM or SIGINT)
pub async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("Failed to install SIGTERM handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {
            tracing::info!("Received Ctrl+C, initiating graceful shutdown");
        }
        _ = terminate => {
            tracing::info!("Received SIGTERM, initiating graceful shutdown");
        }
    }
}

/// Graceful shutdown with timeout
pub async fn graceful_shutdown(timeout: Duration) {
    shutdown_signal().await;
    
    tracing::info!(
        timeout_secs = timeout.as_secs(),
        "Waiting for in-flight requests to complete"
    );
    
    // Give time for connections to drain
    tokio::time::sleep(Duration::from_secs(1)).await;
    
    tracing::info!("Shutdown complete");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_shutdown_controller_creation() {
        let (controller, _rx) = ShutdownController::new();
        let _rx2 = controller.subscribe();
    }

    #[test]
    fn test_shutdown_timeout() {
        assert_eq!(SHUTDOWN_TIMEOUT, Duration::from_secs(30));
    }

    #[tokio::test]
    async fn test_shutdown_broadcast() {
        let (controller, mut rx) = ShutdownController::new();
        
        // Spawn receiver
        let handle = tokio::spawn(async move {
            rx.recv().await.is_ok()
        });
        
        // Send shutdown
        tokio::time::sleep(Duration::from_millis(10)).await;
        controller.shutdown();
        
        // Verify received
        let result = handle.await.unwrap();
        assert!(result);
    }
}
