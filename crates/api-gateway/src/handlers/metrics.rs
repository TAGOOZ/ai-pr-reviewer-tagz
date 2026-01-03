//! Prometheus metrics endpoint for API Gateway
//!
//! Exposes metrics at /metrics in Prometheus format.

use axum::response::{IntoResponse, Response};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::OnceLock;

/// Global metrics registry
static METRICS: OnceLock<Metrics> = OnceLock::new();

/// Metrics storage
pub struct Metrics {
    pub requests_total: AtomicU64,
    pub requests_success: AtomicU64,
    pub requests_error: AtomicU64,
    pub reviews_total: AtomicU64,
    pub reviews_completed: AtomicU64,
    pub reviews_failed: AtomicU64,
    pub cache_hits: AtomicU64,
    pub cache_misses: AtomicU64,
}

impl Default for Metrics {
    fn default() -> Self {
        Self::new()
    }
}

impl Metrics {
    pub fn new() -> Self {
        Self {
            requests_total: AtomicU64::new(0),
            requests_success: AtomicU64::new(0),
            requests_error: AtomicU64::new(0),
            reviews_total: AtomicU64::new(0),
            reviews_completed: AtomicU64::new(0),
            reviews_failed: AtomicU64::new(0),
            cache_hits: AtomicU64::new(0),
            cache_misses: AtomicU64::new(0),
        }
    }

    pub fn global() -> &'static Metrics {
        METRICS.get_or_init(Metrics::new)
    }

    pub fn inc_requests(&self) {
        self.requests_total.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_requests_success(&self) {
        self.requests_success.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_requests_error(&self) {
        self.requests_error.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_reviews(&self) {
        self.reviews_total.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_reviews_completed(&self) {
        self.reviews_completed.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_reviews_failed(&self) {
        self.reviews_failed.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_cache_hit(&self) {
        self.cache_hits.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_cache_miss(&self) {
        self.cache_misses.fetch_add(1, Ordering::Relaxed);
    }
}

/// Handler for /metrics endpoint
/// Returns metrics in Prometheus text format
pub async fn metrics_handler() -> Response {
    let m = Metrics::global();

    let body = format!(
        r#"# HELP coderabbit_requests_total Total number of HTTP requests
# TYPE coderabbit_requests_total counter
coderabbit_requests_total {}

# HELP coderabbit_requests_success_total Total number of successful HTTP requests
# TYPE coderabbit_requests_success_total counter
coderabbit_requests_success_total {}

# HELP coderabbit_requests_error_total Total number of failed HTTP requests
# TYPE coderabbit_requests_error_total counter
coderabbit_requests_error_total {}

# HELP coderabbit_reviews_total Total number of code reviews initiated
# TYPE coderabbit_reviews_total counter
coderabbit_reviews_total {}

# HELP coderabbit_reviews_completed_total Total number of code reviews completed
# TYPE coderabbit_reviews_completed_total counter
coderabbit_reviews_completed_total {}

# HELP coderabbit_reviews_failed_total Total number of code reviews failed
# TYPE coderabbit_reviews_failed_total counter
coderabbit_reviews_failed_total {}

# HELP coderabbit_cache_hits_total Total number of cache hits
# TYPE coderabbit_cache_hits_total counter
coderabbit_cache_hits_total {}

# HELP coderabbit_cache_misses_total Total number of cache misses
# TYPE coderabbit_cache_misses_total counter
coderabbit_cache_misses_total {}
"#,
        m.requests_total.load(Ordering::Relaxed),
        m.requests_success.load(Ordering::Relaxed),
        m.requests_error.load(Ordering::Relaxed),
        m.reviews_total.load(Ordering::Relaxed),
        m.reviews_completed.load(Ordering::Relaxed),
        m.reviews_failed.load(Ordering::Relaxed),
        m.cache_hits.load(Ordering::Relaxed),
        m.cache_misses.load(Ordering::Relaxed),
    );

    Response::builder()
        .header("Content-Type", "text/plain; version=0.0.4")
        .body(body.into())
        .unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_increment() {
        let m = Metrics::new();
        m.inc_requests();
        m.inc_requests();
        assert_eq!(m.requests_total.load(Ordering::Relaxed), 2);
    }

    #[test]
    fn test_metrics_global() {
        let m1 = Metrics::global();
        let m2 = Metrics::global();
        // Same instance
        assert!(std::ptr::eq(m1, m2));
    }
}
