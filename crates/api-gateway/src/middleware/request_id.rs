//! Request ID middleware
//!
//! Assigns unique ID to each request for tracing/logging.

use axum::{
    body::Body,
    http::{header::HeaderName, HeaderValue, Request},
    response::Response,
};
use std::{
    future::Future,
    pin::Pin,
    task::{Context, Poll},
};
use tower::{Layer, Service};
use uuid::Uuid;

/// Header name for request ID
pub const REQUEST_ID_HEADER: &str = "X-Request-ID";

/// Request ID layer
#[derive(Clone, Default)]
pub struct RequestIdLayer;

impl RequestIdLayer {
    pub fn new() -> Self {
        Self
    }
}

impl<S> Layer<S> for RequestIdLayer {
    type Service = RequestIdService<S>;

    fn layer(&self, inner: S) -> Self::Service {
        RequestIdService { inner }
    }
}

/// Request ID service
#[derive(Clone)]
pub struct RequestIdService<S> {
    inner: S,
}

impl<S> Service<Request<Body>> for RequestIdService<S>
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

    fn call(&mut self, mut req: Request<Body>) -> Self::Future {
        // Generate or extract request ID
        let request_id = req
            .headers()
            .get(REQUEST_ID_HEADER)
            .and_then(|v| v.to_str().ok())
            .map(|s| s.to_string())
            .unwrap_or_else(|| Uuid::new_v4().to_string());

        // Add to request headers
        req.headers_mut().insert(
            HeaderName::from_static("x-request-id"),
            HeaderValue::from_str(&request_id).unwrap(),
        );

        // Create span for tracing
        let span = tracing::info_span!(
            "request",
            request_id = %request_id,
            method = %req.method(),
            uri = %req.uri(),
        );

        let mut inner = self.inner.clone();
        let request_id_clone = request_id.clone();

        Box::pin(async move {
            let _guard = span.enter();
            
            let mut response = inner.call(req).await?;
            
            // Add request ID to response headers
            response.headers_mut().insert(
                HeaderName::from_static("x-request-id"),
                HeaderValue::from_str(&request_id_clone).unwrap(),
            );
            
            Ok(response)
        })
    }
}

/// Extract request ID from headers
pub fn get_request_id(req: &Request<Body>) -> Option<String> {
    req.headers()
        .get(REQUEST_ID_HEADER)
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_request_id_header_name() {
        assert_eq!(REQUEST_ID_HEADER, "X-Request-ID");
    }

    #[test]
    fn test_layer_creation() {
        let _layer = RequestIdLayer::new();
    }
}
