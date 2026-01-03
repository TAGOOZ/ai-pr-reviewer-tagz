//! Rate limiting middleware
//!
//! Implements token bucket rate limiting per IP/API key.

use axum::{
    body::Body,
    extract::ConnectInfo,
    http::{Request, StatusCode},
    response::{IntoResponse, Response},
};
use std::{
    collections::HashMap,
    net::SocketAddr,
    sync::{Arc, RwLock},
    time::{Duration, Instant},
};
use tower::{Layer, Service};

/// Rate limit configuration
#[derive(Clone, Debug)]
pub struct RateLimitConfig {
    /// Requests per window
    pub requests_per_window: u32,
    /// Window duration
    pub window: Duration,
}

impl Default for RateLimitConfig {
    fn default() -> Self {
        Self {
            requests_per_window: 100,
            window: Duration::from_secs(60),
        }
    }
}

/// Token bucket for rate limiting
#[derive(Debug)]
struct TokenBucket {
    tokens: u32,
    last_refill: Instant,
    max_tokens: u32,
    refill_rate: Duration,
}

impl TokenBucket {
    fn new(max_tokens: u32, refill_rate: Duration) -> Self {
        Self {
            tokens: max_tokens,
            last_refill: Instant::now(),
            max_tokens,
            refill_rate,
        }
    }

    fn try_acquire(&mut self) -> bool {
        self.refill();
        if self.tokens > 0 {
            self.tokens -= 1;
            true
        } else {
            false
        }
    }

    fn refill(&mut self) {
        let now = Instant::now();
        let elapsed = now.duration_since(self.last_refill);
        
        if elapsed >= self.refill_rate {
            let refills = (elapsed.as_millis() / self.refill_rate.as_millis()) as u32;
            self.tokens = (self.tokens + refills).min(self.max_tokens);
            self.last_refill = now;
        }
    }

    fn remaining(&self) -> u32 {
        self.tokens
    }
}

/// Rate limiter state
pub struct RateLimiter {
    buckets: RwLock<HashMap<String, TokenBucket>>,
    config: RateLimitConfig,
}

impl RateLimiter {
    pub fn new(config: RateLimitConfig) -> Self {
        Self {
            buckets: RwLock::new(HashMap::new()),
            config,
        }
    }

    pub fn check(&self, key: &str) -> RateLimitResult {
        let mut buckets = self.buckets.write().unwrap();
        
        let bucket = buckets.entry(key.to_string()).or_insert_with(|| {
            TokenBucket::new(
                self.config.requests_per_window,
                self.config.window / self.config.requests_per_window,
            )
        });

        if bucket.try_acquire() {
            RateLimitResult::Allowed {
                remaining: bucket.remaining(),
                limit: self.config.requests_per_window,
            }
        } else {
            RateLimitResult::Limited {
                retry_after: self.config.window,
            }
        }
    }
}

pub enum RateLimitResult {
    Allowed { remaining: u32, limit: u32 },
    Limited { retry_after: Duration },
}

/// Rate limit layer
#[derive(Clone)]
pub struct RateLimitLayer {
    limiter: Arc<RateLimiter>,
}

impl RateLimitLayer {
    pub fn new(config: RateLimitConfig) -> Self {
        Self {
            limiter: Arc::new(RateLimiter::new(config)),
        }
    }
}

impl Default for RateLimitLayer {
    fn default() -> Self {
        Self::new(RateLimitConfig::default())
    }
}

impl<S> Layer<S> for RateLimitLayer {
    type Service = RateLimitService<S>;

    fn layer(&self, inner: S) -> Self::Service {
        RateLimitService {
            inner,
            limiter: self.limiter.clone(),
        }
    }
}

/// Rate limit service
#[derive(Clone)]
pub struct RateLimitService<S> {
    inner: S,
    limiter: Arc<RateLimiter>,
}

impl<S> Service<Request<Body>> for RateLimitService<S>
where
    S: Service<Request<Body>, Response = Response> + Clone + Send + 'static,
    S::Future: Send,
{
    type Response = Response;
    type Error = S::Error;
    type Future = std::pin::Pin<Box<dyn std::future::Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, cx: &mut std::task::Context<'_>) -> std::task::Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, req: Request<Body>) -> Self::Future {
        // Extract client identifier (IP or API key)
        let key = extract_rate_limit_key(&req);
        let result = self.limiter.check(&key);
        
        match result {
            RateLimitResult::Allowed { remaining, limit } => {
                let mut inner = self.inner.clone();
                Box::pin(async move {
                    let mut response = inner.call(req).await?;
                    // Add rate limit headers
                    let headers = response.headers_mut();
                    headers.insert("X-RateLimit-Limit", limit.to_string().parse().unwrap());
                    headers.insert("X-RateLimit-Remaining", remaining.to_string().parse().unwrap());
                    Ok(response)
                })
            }
            RateLimitResult::Limited { retry_after } => {
                tracing::warn!(key = %key, "Rate limit exceeded");
                Box::pin(async move {
                    Ok(rate_limit_response(retry_after))
                })
            }
        }
    }
}

fn extract_rate_limit_key(req: &Request<Body>) -> String {
    // Try API key first
    if let Some(api_key) = req.headers().get("X-API-Key") {
        if let Ok(key) = api_key.to_str() {
            return format!("api:{}", key);
        }
    }
    
    // Fall back to IP
    if let Some(forwarded) = req.headers().get("X-Forwarded-For") {
        if let Ok(ips) = forwarded.to_str() {
            if let Some(ip) = ips.split(',').next() {
                return format!("ip:{}", ip.trim());
            }
        }
    }
    
    // Default
    "ip:unknown".to_string()
}

fn rate_limit_response(retry_after: Duration) -> Response {
    (
        StatusCode::TOO_MANY_REQUESTS,
        [
            ("Content-Type", "application/json"),
            ("Retry-After", &retry_after.as_secs().to_string()),
        ],
        r#"{"error": "Rate limit exceeded", "code": "RATE_LIMITED"}"#,
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_token_bucket_acquire() {
        let mut bucket = TokenBucket::new(10, Duration::from_secs(1));
        assert!(bucket.try_acquire());
        assert_eq!(bucket.remaining(), 9);
    }

    #[test]
    fn test_rate_limiter_allows_within_limit() {
        let limiter = RateLimiter::new(RateLimitConfig {
            requests_per_window: 5,
            window: Duration::from_secs(60),
        });
        
        for _ in 0..5 {
            assert!(matches!(limiter.check("test"), RateLimitResult::Allowed { .. }));
        }
    }

    #[test]
    fn test_rate_limiter_blocks_over_limit() {
        let limiter = RateLimiter::new(RateLimitConfig {
            requests_per_window: 2,
            window: Duration::from_secs(60),
        });
        
        assert!(matches!(limiter.check("test"), RateLimitResult::Allowed { .. }));
        assert!(matches!(limiter.check("test"), RateLimitResult::Allowed { .. }));
        assert!(matches!(limiter.check("test"), RateLimitResult::Limited { .. }));
    }
}
