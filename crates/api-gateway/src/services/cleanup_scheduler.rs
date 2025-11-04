/// Cache Cleanup Scheduler
///
/// Background task that periodically cleans up expired cache entries
///
/// **Usage:**
/// Add to your main.rs or application startup:
/// ```rust
/// use crate::services::cleanup_scheduler;
///
/// // In your main function:
/// cleanup_scheduler::start_cleanup_scheduler();
/// ```

use tokio::time::{interval, Duration};
use tracing;

/// Start the cache cleanup scheduler
///
/// Runs every hour to:
/// - Remove expired cache entries (>24 hours old)
/// - Evict entries if cache exceeds size limit
/// - Evict entries if cache exceeds count limit
///
/// **Note:** This function spawns a background task and returns immediately.
/// The cleanup task will run for the lifetime of the application.
pub fn start_cleanup_scheduler() {
    tokio::spawn(async move {
        // Wait 5 minutes before first run (give app time to start)
        tokio::time::sleep(Duration::from_secs(300)).await;

        let mut interval = interval(Duration::from_secs(3600)); // 1 hour

        tracing::info!("🧹 Cache cleanup scheduler started (runs every hour)");

        loop {
            interval.tick().await;

            tracing::info!("🧹 Running scheduled cache cleanup...");

            match run_cleanup_cycle().await {
                Ok(stats) => {
                    tracing::info!("✅ Cache cleanup complete: {}", stats);
                }
                Err(e) => {
                    tracing::error!("❌ Cache cleanup failed: {}", e);
                }
            }
        }
    });
}

/// Run a single cleanup cycle
///
/// This function is separated so it can be called manually for testing
/// or on-demand cleanup.
async fn run_cleanup_cycle() -> Result<String, String> {
    use crate::handlers::webhook::HYBRID_ANALYZER;

    // Access the global analyzer
    let mut analyzer_guard = HYBRID_ANALYZER.lock().await;

    if let Some(analyzer) = analyzer_guard.as_mut() {
        // Run cleanup
        analyzer.cleanup_cache().await?;

        // Get stats
        let stats = analyzer.get_cache_stats();

        Ok(stats)
    } else {
        // Analyzer not initialized yet - this is OK during startup
        Ok("Analyzer not initialized yet (no repositories cached)".to_string())
    }
}

/// Manually trigger a cleanup cycle (for testing or admin endpoints)
pub async fn trigger_cleanup() -> Result<String, String> {
    tracing::info!("Manual cleanup triggered");
    run_cleanup_cycle().await
}

/// Get current cache statistics (for monitoring/health endpoints)
pub async fn get_cache_stats() -> Result<String, String> {
    use crate::handlers::webhook::HYBRID_ANALYZER;

    let analyzer_guard = HYBRID_ANALYZER.lock().await;

    if let Some(analyzer) = analyzer_guard.as_ref() {
        Ok(analyzer.get_cache_stats())
    } else {
        Ok("Analyzer not initialized (0 repos, 0 GB)".to_string())
    }
}
