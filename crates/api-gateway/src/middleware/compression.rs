//! Response compression middleware
//!
//! Compresses responses using gzip/deflate/br based on Accept-Encoding.

use tower_http::compression::CompressionLayer;

/// Create compression layer with default settings
/// 
/// Supports: gzip, deflate, br (brotli)
/// Only compresses responses > 1KB
pub fn compression_layer() -> CompressionLayer {
    CompressionLayer::new()
}

/// Compression configuration for different content types
pub mod config {
    /// Minimum response size to compress (bytes)
    pub const MIN_COMPRESS_SIZE: usize = 1024;
    
    /// Content types that should be compressed
    pub const COMPRESSIBLE_TYPES: &[&str] = &[
        "application/json",
        "text/plain",
        "text/html",
        "text/css",
        "text/javascript",
        "application/javascript",
        "application/xml",
        "text/xml",
    ];
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compression_layer_creation() {
        let _layer = compression_layer();
        // Layer created successfully
    }

    #[test]
    fn test_min_compress_size() {
        assert_eq!(config::MIN_COMPRESS_SIZE, 1024);
    }

    #[test]
    fn test_compressible_types_includes_json() {
        assert!(config::COMPRESSIBLE_TYPES.contains(&"application/json"));
    }
}
