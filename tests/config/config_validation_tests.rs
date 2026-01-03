use coderabbit_shared::config::{AppConfig, SecurityConfig, SandboxConfig, FeatureFlags};
use std::env;

#[test]
fn test_config_security_default() {
    let security = SecurityConfig::default();
    
    assert_eq!(security.enable_cors, true);
    assert_eq!(security.allowed_origins, "http://localhost:3000");
    assert_eq!(security.rate_limit_requests_per_minute, 60);
    assert_eq!(security.enable_secret_scanning, true);
}

#[test]
fn test_config_sandbox_default() {
    let sandbox = SandboxConfig::default();
    
    assert_eq!(sandbox.execution_timeout, 30);
    assert_eq!(sandbox.max_memory_mb, 512);
    assert_eq!(sandbox.max_cpus, 1.0);
    assert_eq!(sandbox.max_processes, 50);
    assert_eq!(sandbox.docker_image, "coderabbit-sandbox:latest");
}

#[test]
fn test_config_feature_flags_default() {
    let flags = FeatureFlags::default();
    
    assert_eq!(flags.enable_security_scanning, true);
    assert_eq!(flags.enable_ai_review, true);
    assert_eq!(flags.enable_vector_search, true);
    assert_eq!(flags.enable_metrics, true);
    assert_eq!(flags.enable_pr_test_runner, false);
    assert_eq!(flags.enable_deepwiki_integration, true);
    assert_eq!(flags.enable_devin_integration, false);
}
