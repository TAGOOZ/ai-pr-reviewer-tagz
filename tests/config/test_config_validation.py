"""Tests for configuration validation."""

import pytest
import os
from coderabbit_ai.config_validator import (
    validate_config_from_env,
    ServiceConfig,
    ServerConfig,
    TimeoutConfig,
    SandboxConfig,
    TextProcessingConfig,
    SecurityThresholdsConfig,
    FeatureFlags,
)


class TestConfigValidation:
    """Test configuration validation."""

    def test_service_config_default(self):
        """Test service configuration defaults."""
        config = ServiceConfig()
        
        assert config.embedding_service_url == "http://localhost:8081/embed"
        assert config.vector_search_service_url == "http://localhost:8082/search"

    def test_service_config_url_validation(self):
        """Test service URL validation."""
        # Valid URLs
        valid_config = ServiceConfig(
            embedding_service_url="https://api.example.com/embed",
            vector_search_service_url="http://localhost:8082/search"
        )
        assert valid_config.embedding_service_url == "https://api.example.com/embed"
        
        # Invalid URL should raise validation error
        with pytest.raises(ValueError, match="Invalid URL format"):
            ServiceConfig(
                embedding_service_url="invalid-url",
                vector_search_service_url="http://localhost:8082/search"
            )

    def test_server_config_default(self):
        """Test server configuration defaults."""
        config = ServerConfig()
        
        assert config.host == "127.0.0.1"
        assert config.port == 8081
        assert config.workers == 1

    def test_server_config_validation(self):
        """Test server configuration validation."""
        # Valid configuration
        valid_config = ServerConfig(host="0.0.0.0", port=9000, workers=4)
        assert valid_config.port == 9000
        assert valid_config.workers == 4
        
        # Invalid port should raise error
        with pytest.raises(ValueError, match="ensure this value is greater than or equal to 1"):
            ServerConfig(host="0.0.0.0", port=0, workers=1)
        
        # Invalid port > 65535 should raise error
        with pytest.raises(ValueError, match="ensure this value is less than or equal to 65535"):
            ServerConfig(host="0.0.0.0", port=65536, workers=1)

    def test_timeout_config_default(self):
        """Test timeout configuration defaults."""
        config = TimeoutConfig()
        
        assert config.http_request_timeout == 10
        assert config.static_analyzer_timeout == 30
        assert config.agent_execution_timeout == 300
        assert config.sandbox_execution_timeout == 30

    def test_sandbox_config_default(self):
        """Test sandbox configuration defaults."""
        config = SandboxConfig()
        
        assert config.max_memory_mb == 512
        assert config.max_cpus == 1.0
        assert config.max_processes == 50
        assert config.docker_image == "coderabbit-sandbox:latest"

    def test_text_processing_config_default(self):
        """Test text processing configuration defaults."""
        config = TextProcessingConfig()
        
        assert config.truncate_error_output == 1000
        assert config.truncate_sandbox_output == 1000
        assert config.truncate_static_context == 1000
        assert config.truncate_code_changes == 5000
        assert config.truncate_verification_text == 6000

    def test_feature_flags_default(self):
        """Test feature flags defaults."""
        flags = FeatureFlags()
        
        assert flags.enable_security_scanning == True
        assert flags.enable_ai_review == True
        assert flags.enable_vector_search == True
        assert flags.enable_metrics == True
        assert flags.enable_pr_test_runner == False
        assert flags.enable_deepwiki_integration == True
        assert flags.enable_devin_integration == False


class TestConfigFromEnv:
    """Test configuration loading from environment."""

    def test_load_config_with_env(self):
        """Test loading config from environment variables."""
        # Set environment variables
        os.environ["OPENAI_API_KEY"] = "test-key-at-least-10-chars"
        os.environ["HOST"] = "192.168.1.1"
        os.environ["PORT"] = "9000"
        
        try:
            config = validate_config_from_env()
            
            assert config.server.host == "192.168.1.1"
            assert config.server.port == 9000
        finally:
            # Cleanup
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("HOST", None)
            os.environ.pop("PORT", None)

    def test_config_production_hardening(self):
        """Test production hardening warnings."""
        os.environ["ENVIRONMENT"] = "production"
        os.environ["OPENAI_API_KEY"] = "sk-too-short"
        
        try:
            config = validate_config_from_env()
            warnings = config.validate_production_hardening()
            
            # Should have warnings for too short API key
            assert len(warnings) > 0
            assert any("API_KEY appears too short" in w for w in warnings)
        finally:
            os.environ.pop("ENVIRONMENT", None)
            os.environ.pop("OPENAI_API_KEY", None)

    def test_config_to_dict(self):
        """Test converting configuration to dictionary."""
        config = validate_config_from_env()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert "server" in config_dict
        assert "timeouts" in config_dict
        assert "sandbox" in config_dict
        assert "feature_flags" in config_dict


class TestSecurityThresholds:
    """Test security thresholds configuration."""

    def test_security_thresholds_default(self):
        """Test security thresholds defaults."""
        config = SecurityThresholdsConfig()
        
        assert config.block_on_critical == True
        assert config.max_high_severity == 3
        assert config.confidence_threshold == 0.7

    def test_security_thresholds_validation(self):
        """Test security thresholds validation."""
        # Valid configuration
        valid_config = SecurityThresholdsConfig(
            block_on_critical=True,
            max_high_severity=10,
            confidence_threshold=0.9
        )
        assert valid_config.confidence_threshold == 0.9
        
        # Invalid confidence (too high)
        with pytest.raises(ValueError, match="ensure this value is less than or equal to 1.0"):
            SecurityThresholdsConfig(
                block_on_critical=True,
                max_high_severity=10,
                confidence_threshold=1.5
            )
        
        # Invalid confidence (too low)
        with pytest.raises(ValueError, match="ensure this value is greater than or equal to 0.0"):
            SecurityThresholdsConfig(
                block_on_critical=True,
                max_high_severity=10,
                confidence_threshold=-0.1
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
