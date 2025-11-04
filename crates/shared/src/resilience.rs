///! Resilience patterns: Circuit Breaker, Retry, Timeout, Bulkhead
///! Production-grade error handling and fallback mechanisms

use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::time::timeout;
use tracing::{info, warn, error};

/// Circuit Breaker states
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CircuitState {
    Closed,   // Normal operation
    Open,     // Failing, rejecting requests
    HalfOpen, // Testing if service recovered
}

/// Circuit Breaker for preventing cascading failures
#[derive(Debug, Clone)]
pub struct CircuitBreaker {
    name: String,
    state: Arc<AtomicUsize>,
    failure_count: Arc<AtomicU64>,
    success_count: Arc<AtomicU64>,
    last_failure_time: Arc<AtomicU64>,
    config: CircuitBreakerConfig,
}

#[derive(Debug, Clone)]
pub struct CircuitBreakerConfig {
    pub failure_threshold: u64,
    pub success_threshold: u64,
    pub timeout_duration: Duration,
    pub reset_timeout: Duration,
}

impl Default for CircuitBreakerConfig {
    fn default() -> Self {
        Self {
            failure_threshold: 5,      // Open after 5 failures
            success_threshold: 2,       // Close after 2 successes
            timeout_duration: Duration::from_secs(30),
            reset_timeout: Duration::from_secs(60),
        }
    }
}

impl CircuitBreaker {
    pub fn new(name: impl Into<String>, config: CircuitBreakerConfig) -> Self {
        Self {
            name: name.into(),
            state: Arc::new(AtomicUsize::new(CircuitState::Closed as usize)),
            failure_count: Arc::new(AtomicU64::new(0)),
            success_count: Arc::new(AtomicU64::new(0)),
            last_failure_time: Arc::new(AtomicU64::new(0)),
            config,
        }
    }

    pub fn get_state(&self) -> CircuitState {
        match self.state.load(Ordering::Relaxed) {
            0 => CircuitState::Closed,
            1 => CircuitState::Open,
            2 => CircuitState::HalfOpen,
            _ => CircuitState::Closed,
        }
    }

    fn set_state(&self, state: CircuitState) {
        self.state.store(state as usize, Ordering::Relaxed);
        info!("[CircuitBreaker:{}] State changed to {:?}", self.name, state);
    }

    pub async fn call<F, Fut, T, E>(&self, f: F) -> Result<T, CircuitBreakerError<E>>
    where
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = Result<T, E>>,
    {
        // Check if circuit is open
        let current_state = self.get_state();

        match current_state {
            CircuitState::Open => {
                // Check if reset timeout has passed
                let last_failure = self.last_failure_time.load(Ordering::Relaxed);
                let now = Instant::now().elapsed().as_millis() as u64;

                if now - last_failure > self.config.reset_timeout.as_millis() as u64 {
                    info!("[CircuitBreaker:{}] Reset timeout passed, transitioning to HalfOpen", self.name);
                    self.set_state(CircuitState::HalfOpen);
                } else {
                    warn!("[CircuitBreaker:{}] Circuit is OPEN, rejecting request", self.name);
                    return Err(CircuitBreakerError::Open);
                }
            }
            CircuitState::HalfOpen => {
                info!("[CircuitBreaker:{}] In HalfOpen state, testing service", self.name);
            }
            CircuitState::Closed => {
                // Normal operation
            }
        }

        // Execute the function with timeout
        let result = timeout(self.config.timeout_duration, f()).await;

        match result {
            Ok(Ok(value)) => {
                self.on_success();
                Ok(value)
            }
            Ok(Err(err)) => {
                self.on_failure();
                Err(CircuitBreakerError::Execution(err))
            }
            Err(_) => {
                self.on_failure();
                Err(CircuitBreakerError::Timeout)
            }
        }
    }

    fn on_success(&self) {
        let successes = self.success_count.fetch_add(1, Ordering::Relaxed) + 1;

        match self.get_state() {
            CircuitState::HalfOpen => {
                if successes >= self.config.success_threshold {
                    info!("[CircuitBreaker:{}] Success threshold reached, closing circuit", self.name);
                    self.set_state(CircuitState::Closed);
                    self.failure_count.store(0, Ordering::Relaxed);
                    self.success_count.store(0, Ordering::Relaxed);
                }
            }
            CircuitState::Closed => {
                // Reset failure count on success
                self.failure_count.store(0, Ordering::Relaxed);
            }
            _ => {}
        }
    }

    fn on_failure(&self) {
        let failures = self.failure_count.fetch_add(1, Ordering::Relaxed) + 1;
        self.last_failure_time.store(
            Instant::now().elapsed().as_millis() as u64,
            Ordering::Relaxed,
        );

        match self.get_state() {
            CircuitState::Closed => {
                if failures >= self.config.failure_threshold {
                    warn!("[CircuitBreaker:{}] Failure threshold reached, opening circuit", self.name);
                    self.set_state(CircuitState::Open);
                    self.success_count.store(0, Ordering::Relaxed);
                }
            }
            CircuitState::HalfOpen => {
                warn!("[CircuitBreaker:{}] Failure in HalfOpen state, reopening circuit", self.name);
                self.set_state(CircuitState::Open);
                self.success_count.store(0, Ordering::Relaxed);
            }
            _ => {}
        }
    }

    pub fn get_metrics(&self) -> CircuitBreakerMetrics {
        CircuitBreakerMetrics {
            name: self.name.clone(),
            state: self.get_state(),
            failure_count: self.failure_count.load(Ordering::Relaxed),
            success_count: self.success_count.load(Ordering::Relaxed),
        }
    }
}

#[derive(Debug)]
pub enum CircuitBreakerError<E> {
    Open,
    Timeout,
    Execution(E),
}

#[derive(Debug, Clone)]
pub struct CircuitBreakerMetrics {
    pub name: String,
    pub state: CircuitState,
    pub failure_count: u64,
    pub success_count: u64,
}

/// Retry policy with exponential backoff
#[derive(Debug, Clone)]
pub struct RetryPolicy {
    pub max_retries: u32,
    pub initial_delay: Duration,
    pub max_delay: Duration,
    pub backoff_multiplier: f64,
}

impl Default for RetryPolicy {
    fn default() -> Self {
        Self {
            max_retries: 3,
            initial_delay: Duration::from_millis(100),
            max_delay: Duration::from_secs(30),
            backoff_multiplier: 2.0,
        }
    }
}

impl RetryPolicy {
    pub async fn execute<F, Fut, T, E>(&self, mut f: F) -> Result<T, E>
    where
        F: FnMut() -> Fut,
        Fut: std::future::Future<Output = Result<T, E>>,
        E: std::fmt::Debug,
    {
        let mut attempt = 0;
        let mut delay = self.initial_delay;

        loop {
            match f().await {
                Ok(value) => return Ok(value),
                Err(err) => {
                    attempt += 1;

                    if attempt >= self.max_retries {
                        error!("Max retries ({}) exceeded, giving up", self.max_retries);
                        return Err(err);
                    }

                    warn!("Attempt {} failed: {:?}, retrying after {:?}", attempt, err, delay);

                    tokio::time::sleep(delay).await;

                    // Exponential backoff
                    delay = Duration::from_millis(
                        (delay.as_millis() as f64 * self.backoff_multiplier).min(self.max_delay.as_millis() as f64) as u64
                    );
                }
            }
        }
    }
}

/// Bulkhead pattern for resource isolation
#[derive(Debug, Clone)]
pub struct Bulkhead {
    name: String,
    max_concurrent: Arc<AtomicUsize>,
    current_concurrent: Arc<AtomicUsize>,
}

impl Bulkhead {
    pub fn new(name: impl Into<String>, max_concurrent: usize) -> Self {
        Self {
            name: name.into(),
            max_concurrent: Arc::new(AtomicUsize::new(max_concurrent)),
            current_concurrent: Arc::new(AtomicUsize::new(0)),
        }
    }

    pub async fn call<F, Fut, T>(&self, f: F) -> Result<T, BulkheadError>
    where
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = T>,
    {
        // Acquire slot
        let current = self.current_concurrent.fetch_add(1, Ordering::Relaxed);
        let max = self.max_concurrent.load(Ordering::Relaxed);

        if current >= max {
            self.current_concurrent.fetch_sub(1, Ordering::Relaxed);
            warn!("[Bulkhead:{}] Capacity exceeded ({}/{}), rejecting request", self.name, current, max);
            return Err(BulkheadError::CapacityExceeded);
        }

        // Execute function
        let result = f().await;

        // Release slot
        self.current_concurrent.fetch_sub(1, Ordering::Relaxed);

        Ok(result)
    }

    pub fn get_metrics(&self) -> BulkheadMetrics {
        BulkheadMetrics {
            name: self.name.clone(),
            max_concurrent: self.max_concurrent.load(Ordering::Relaxed),
            current_concurrent: self.current_concurrent.load(Ordering::Relaxed),
        }
    }
}

#[derive(Debug)]
pub enum BulkheadError {
    CapacityExceeded,
}

#[derive(Debug, Clone)]
pub struct BulkheadMetrics {
    pub name: String,
    pub max_concurrent: usize,
    pub current_concurrent: usize,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_circuit_breaker_opens_on_failures() {
        let config = CircuitBreakerConfig {
            failure_threshold: 3,
            success_threshold: 2,
            timeout_duration: Duration::from_secs(1),
            reset_timeout: Duration::from_secs(5),
        };

        let cb = CircuitBreaker::new("test", config);

        // Simulate failures
        for _ in 0..3 {
            let result = cb.call(|| async { Err::<(), _>("error") }).await;
            assert!(result.is_err());
        }

        // Circuit should be open now
        assert_eq!(cb.get_state(), CircuitState::Open);

        // Further calls should be rejected immediately
        let result = cb.call(|| async { Ok::<_, ()>(()) }).await;
        assert!(matches!(result, Err(CircuitBreakerError::Open)));
    }

    #[tokio::test]
    async fn test_retry_policy() {
        let policy = RetryPolicy {
            max_retries: 3,
            initial_delay: Duration::from_millis(10),
            max_delay: Duration::from_millis(100),
            backoff_multiplier: 2.0,
        };

        let mut attempts = 0;

        let result = policy.execute(|| {
            attempts += 1;
            async move {
                if attempts < 3 {
                    Err("not yet")
                } else {
                    Ok("success")
                }
            }
        }).await;

        assert_eq!(result, Ok("success"));
        assert_eq!(attempts, 3);
    }

    #[tokio::test]
    async fn test_bulkhead_limits_concurrent_requests() {
        let bulkhead = Bulkhead::new("test", 2);

        let b1 = bulkhead.clone();
        let b2 = bulkhead.clone();
        let b3 = bulkhead.clone();

        // Start 2 concurrent tasks
        let task1 = tokio::spawn(async move {
            b1.call(|| async {
                tokio::time::sleep(Duration::from_millis(100)).await;
                "task1"
            }).await
        });

        let task2 = tokio::spawn(async move {
            b2.call(|| async {
                tokio::time::sleep(Duration::from_millis(100)).await;
                "task2"
            }).await
        });

        tokio::time::sleep(Duration::from_millis(10)).await;

        // Third task should be rejected
        let result = b3.call(|| async { "task3" }).await;
        assert!(matches!(result, Err(BulkheadError::CapacityExceeded)));

        // Original tasks should complete
        assert!(task1.await.is_ok());
        assert!(task2.await.is_ok());
    }
}
