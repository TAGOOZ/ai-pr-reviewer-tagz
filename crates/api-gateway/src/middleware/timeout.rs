//! Request timeout middleware
//!
//! Enforces request timeouts to prevent hung requests.

use axum::{
    body::Body,
    http::{Request, StatusCode},
    response::{IntoResponse, Response},
};
use std::{
    future::Future,
    pin::Pin,
    task::{Context, Poll},
    time::Duration,
};
use tower::{Layer, Service};

/// Default request timeout (30 seconds)
pub const DEFAULT_TIMEOUT: Duration = Duration::from_secs(30);

/// Long operation timeout (5 minutes) - for reviews
pub const LONG_TIMEOUT: Duration = Duration::from_secs(300);

/// Timeout layer
#[derive(Clone)]
pub struct TimeoutLayer {
    timeout: Duration,
}

impl TimeoutLayer {
    pub fn new(timeout: Duration) -> Self {
        Self { timeout }
    }
}

impl Default for TimeoutLayer {
    fn default() -> Self {
        Self::new(DEFAULT_TIMEOUT)
    }
}

impl<S> Layer<S> for TimeoutLayer {
    type Service = TimeoutService<S>;

    fn layer(&self, inner: S) -> Self::Service {
        TimeoutService {
            inner,
            timeout: self.timeout,
        }
    }
}

/// Timeout service wrapper
#[derive(Clone)]
pub struct TimeoutService<S> {
    inner: S,
    timeout: Duration,
}

impl<S> Service<Request<Body>> for TimeoutService<S>
where
    S: Service<Request<Body>, Response = Response> + Clone + Send + 'static,
    S::Future: Send,
{
    type Response = Response;
    type Error = S::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, req: Request<Body>) -> Self::Future {
        let timeout = self.timeout;
        let mut inner = self.inner.clone();

        Box::pin(async move {
            match tokio::time::timeout(timeout, inner.call(req)).await {
                Ok(result) => result,
                Err(_) => {
                    tracing::warn!(timeout_secs = timeout.as_secs(), "Request timed out");
                    Ok(timeout_response())
                }
            }
        })
    }
}

fn timeout_response() -> Response {
    (
        StatusCode::GATEWAY_TIMEOUT,
        [("Content-Type", "application/json")],
        r#"{"error": "Request timed out", "code": "TIMEOUT"}"#,
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_timeout() {
        let layer = TimeoutLayer::default();
        assert_eq!(layer.timeout, DEFAULT_TIMEOUT);
    }

    #[test]
    fn test_custom_timeout() {
        let layer = TimeoutLayer::new(Duration::from_secs(60));
        assert_eq!(layer.timeout, Duration::from_secs(60));
    }
}
