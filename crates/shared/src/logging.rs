//! Structured JSON logging for CodeRabbit
//!
//! Provides structured logging with request IDs, JSON format for production,
//! and pretty printing for development.

use std::env;
use tracing_subscriber::{
    fmt::{self, format::FmtSpan},
    layer::SubscriberExt,
    util::SubscriberInitExt,
    EnvFilter,
};

/// Initialize logging based on environment
///
/// - Development: Pretty colored output
/// - Production: JSON structured output
pub fn init_logging() {
    let env = env::var("CODERABBIT_ENV").unwrap_or_else(|_| "development".to_string());
    let log_level = env::var("RUST_LOG").unwrap_or_else(|_| "info,coderabbit=debug".to_string());

    let filter = EnvFilter::try_from_default_env()
        .or_else(|_| EnvFilter::try_new(&log_level))
        .unwrap_or_else(|_| EnvFilter::new("info"));

    if env == "production" {
        // JSON format for production (log aggregation)
        tracing_subscriber::registry()
            .with(filter)
            .with(
                fmt::layer()
                    .json()
                    .with_target(true)
                    .with_thread_ids(true)
                    .with_file(true)
                    .with_line_number(true)
                    .with_span_events(FmtSpan::CLOSE),
            )
            .init();
    } else {
        // Pretty format for development
        tracing_subscriber::registry()
            .with(filter)
            .with(
                fmt::layer()
                    .pretty()
                    .with_target(true)
                    .with_thread_ids(false)
                    .with_file(true)
                    .with_line_number(true),
            )
            .init();
    }

    tracing::info!(
        environment = %env,
        log_level = %log_level,
        "Logging initialized"
    );
}

/// Create a span with request ID for tracing
#[macro_export]
macro_rules! request_span {
    ($request_id:expr) => {
        tracing::info_span!("request", request_id = %$request_id)
    };
    ($request_id:expr, $($field:tt)*) => {
        tracing::info_span!("request", request_id = %$request_id, $($field)*)
    };
}

/// Log structured error with context
#[macro_export]
macro_rules! log_error {
    ($err:expr, $($field:tt)*) => {
        tracing::error!(
            error = %$err,
            error_type = std::any::type_name_of_val(&$err),
            $($field)*
        )
    };
    ($err:expr) => {
        tracing::error!(
            error = %$err,
            error_type = std::any::type_name_of_val(&$err),
        )
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_env_filter_parsing() {
        let filter = EnvFilter::try_new("info,coderabbit=debug");
        assert!(filter.is_ok());
    }

    #[test]
    fn test_env_filter_default() {
        let filter = EnvFilter::try_new("info");
        assert!(filter.is_ok());
    }
}
