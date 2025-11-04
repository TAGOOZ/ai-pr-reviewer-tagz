"""Configuration models for organization settings and pipeline configuration."""

from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field, validator
from enum import Enum
from .models import Platform, Severity


class ReviewScope(str, Enum):
    """Scope of code review."""
    FULL = "full"  # Review all changes
    DIFF_ONLY = "diff_only"  # Review only changed lines
    CONTEXT_AWARE = "context_aware"  # Review changes with surrounding context


class AgentType(str, Enum):
    """Types of verification agents."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    LOGIC = "logic"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ACCESSIBILITY = "accessibility"
    MAINTAINABILITY = "maintainability"
    ARCHITECTURE = "architecture"
    COMPLIANCE = "compliance"


class NotificationChannel(str, Enum):
    """Notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class OrganizationTier(str, Enum):
    """Organization subscription tiers."""
    FREE = "free"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class ReviewRuleConfig(BaseModel):
    """Individual review rule configuration."""
    rule_id: str
    enabled: bool = True
    severity: Severity = Severity.MEDIUM
    custom_message: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class LanguageConfig(BaseModel):
    """Language-specific configuration."""
    language: str
    enabled: bool = True
    linters: List[str] = Field(default_factory=list)
    custom_rules: List[ReviewRuleConfig] = Field(default_factory=list)
    style_guide: Optional[str] = None


class AgentConfig(BaseModel):
    """Configuration for verification agents."""
    agent_type: AgentType
    enabled: bool = True
    priority: int = Field(ge=1, le=10, default=5)
    confidence_threshold: float = Field(ge=0.0, le=1.0, default=0.7)
    custom_prompts: Dict[str, str] = Field(default_factory=dict)
    specialization_rules: List[str] = Field(default_factory=list)


class ModelConfig(BaseModel):
    """AI model configuration."""
    model_name: str
    enabled: bool = True
    cost_per_token: float = Field(ge=0.0)
    max_tokens: int = Field(gt=0, default=4000)
    temperature: float = Field(ge=0.0, le=2.0, default=0.7)
    use_cases: List[str] = Field(default_factory=list)  # e.g., ["security", "performance"]


class BudgetConfig(BaseModel):
    """Budget configuration for AI usage."""
    daily_budget_usd: float = Field(ge=0.0, default=100.0)
    monthly_budget_usd: float = Field(ge=0.0, default=3000.0)
    cost_per_review_limit: float = Field(ge=0.0, default=5.0)
    enable_budget_alerts: bool = True
    alert_thresholds: List[float] = Field(default_factory=lambda: [0.5, 0.8, 0.95])


class QualityConfig(BaseModel):
    """Quality assurance configuration."""
    min_confidence_score: float = Field(ge=0.0, le=1.0, default=0.6)
    require_consensus: bool = True
    min_consensus_score: float = Field(ge=0.0, le=1.0, default=0.7)
    enable_false_positive_detection: bool = True
    quality_metrics_tracking: bool = True


class NotificationConfig(BaseModel):
    """Notification configuration."""
    channels: List[NotificationChannel] = Field(default_factory=list)
    webhook_url: Optional[str] = None
    slack_webhook: Optional[str] = None
    email_recipients: List[str] = Field(default_factory=list)
    notification_triggers: List[str] = Field(default_factory=lambda: ["review_complete", "high_severity_issue"])


class SecurityConfig(BaseModel):
    """Security configuration."""
    enable_sandboxing: bool = True
    sandbox_timeout_seconds: int = Field(ge=30, le=600, default=300)
    allowed_file_types: Set[str] = Field(default_factory=lambda: {".py", ".js", ".ts", ".java", ".go", ".rs"})
    blocked_patterns: List[str] = Field(default_factory=list)
    enable_secret_scanning: bool = True
    audit_logging: bool = True


class PerformanceConfig(BaseModel):
    """Performance configuration."""
    max_files_per_review: int = Field(ge=1, le=1000, default=100)
    max_review_time_minutes: int = Field(ge=1, le=60, default=15)
    parallel_processing: bool = True
    max_parallel_agents: int = Field(ge=1, le=20, default=10)
    cache_enabled: bool = True
    cache_ttl_hours: int = Field(ge=1, le=168, default=24)


class IntegrationConfig(BaseModel):
    """Platform integration configuration."""
    platform: Platform
    enabled: bool = True
    webhook_secret: str
    api_token: str
    base_url: Optional[str] = None  # For self-hosted instances
    custom_headers: Dict[str, str] = Field(default_factory=dict)
    rate_limit_per_hour: int = Field(ge=1, default=5000)


class ComplianceConfig(BaseModel):
    """Compliance and audit configuration."""
    soc2_compliance: bool = False
    data_retention_days: int = Field(ge=1, le=2555, default=365)  # Max 7 years
    zero_retention_mode: bool = False
    audit_trail_enabled: bool = True
    encryption_at_rest: bool = True
    encryption_in_transit: bool = True


class AdvancedOrganizationConfig(BaseModel):
    """Advanced organization configuration."""
    organization_id: str
    organization_name: str
    tier: OrganizationTier = OrganizationTier.FREE
    
    # Core Configuration
    review_scope: ReviewScope = ReviewScope.CONTEXT_AWARE
    languages: List[LanguageConfig] = Field(default_factory=list)
    agents: List[AgentConfig] = Field(default_factory=list)
    models: List[ModelConfig] = Field(default_factory=list)
    
    # Operational Configuration
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    
    # Platform Integrations
    integrations: List[IntegrationConfig] = Field(default_factory=list)
    
    # Custom Configuration
    custom_rules: List[ReviewRuleConfig] = Field(default_factory=list)
    custom_prompts: Dict[str, str] = Field(default_factory=dict)
    feature_flags: Dict[str, bool] = Field(default_factory=dict)
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: str = "1.0"

    @validator('agents')
    def validate_agents(cls, v):
        """Ensure no duplicate agent types."""
        agent_types = [agent.agent_type for agent in v]
        if len(agent_types) != len(set(agent_types)):
            raise ValueError("Duplicate agent types are not allowed")
        return v

    @validator('integrations')
    def validate_integrations(cls, v):
        """Ensure no duplicate platform integrations."""
        platforms = [integration.platform for integration in v]
        if len(platforms) != len(set(platforms)):
            raise ValueError("Duplicate platform integrations are not allowed")
        return v

    def get_enabled_agents(self) -> List[AgentConfig]:
        """Get list of enabled agents."""
        return [agent for agent in self.agents if agent.enabled]

    def get_agent_by_type(self, agent_type: AgentType) -> Optional[AgentConfig]:
        """Get agent configuration by type."""
        for agent in self.agents:
            if agent.agent_type == agent_type:
                return agent
        return None

    def get_integration_by_platform(self, platform: Platform) -> Optional[IntegrationConfig]:
        """Get integration configuration by platform."""
        for integration in self.integrations:
            if integration.platform == platform:
                return integration
        return None

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature flag is enabled."""
        return self.feature_flags.get(feature_name, False)


# Default configurations for different tiers
def get_default_free_config(org_id: str, org_name: str) -> AdvancedOrganizationConfig:
    """Get default configuration for free tier."""
    return AdvancedOrganizationConfig(
        organization_id=org_id,
        organization_name=org_name,
        tier=OrganizationTier.FREE,
        agents=[
            AgentConfig(agent_type=AgentType.SECURITY, priority=1),
            AgentConfig(agent_type=AgentType.STYLE, priority=2),
            AgentConfig(agent_type=AgentType.LOGIC, priority=3),
        ],
        budget=BudgetConfig(daily_budget_usd=10.0, monthly_budget_usd=300.0),
        performance=PerformanceConfig(max_files_per_review=50, max_parallel_agents=3)
    )


def get_default_professional_config(org_id: str, org_name: str) -> AdvancedOrganizationConfig:
    """Get default configuration for professional tier."""
    return AdvancedOrganizationConfig(
        organization_id=org_id,
        organization_name=org_name,
        tier=OrganizationTier.PROFESSIONAL,
        agents=[
            AgentConfig(agent_type=AgentType.SECURITY, priority=1),
            AgentConfig(agent_type=AgentType.PERFORMANCE, priority=2),
            AgentConfig(agent_type=AgentType.STYLE, priority=3),
            AgentConfig(agent_type=AgentType.LOGIC, priority=4),
            AgentConfig(agent_type=AgentType.TESTING, priority=5),
            AgentConfig(agent_type=AgentType.DOCUMENTATION, priority=6),
        ],
        budget=BudgetConfig(daily_budget_usd=50.0, monthly_budget_usd=1500.0),
        performance=PerformanceConfig(max_files_per_review=200, max_parallel_agents=6)
    )


def get_default_enterprise_config(org_id: str, org_name: str) -> AdvancedOrganizationConfig:
    """Get default configuration for enterprise tier."""
    return AdvancedOrganizationConfig(
        organization_id=org_id,
        organization_name=org_name,
        tier=OrganizationTier.ENTERPRISE,
        agents=[
            AgentConfig(agent_type=agent_type, priority=i+1) 
            for i, agent_type in enumerate(AgentType)
        ],
        budget=BudgetConfig(daily_budget_usd=200.0, monthly_budget_usd=6000.0),
        performance=PerformanceConfig(max_files_per_review=1000, max_parallel_agents=10),
        security=SecurityConfig(enable_sandboxing=True, audit_logging=True),
        compliance=ComplianceConfig(soc2_compliance=True, audit_trail_enabled=True)
    )


__all__ = [
    # Enums
    "ReviewScope", "AgentType", "NotificationChannel", "OrganizationTier",
    
    # Configuration Models
    "ReviewRuleConfig", "LanguageConfig", "AgentConfig", "ModelConfig",
    "BudgetConfig", "QualityConfig", "NotificationConfig", "SecurityConfig",
    "PerformanceConfig", "IntegrationConfig", "ComplianceConfig",
    "AdvancedOrganizationConfig",
    
    # Default Configurations
    "get_default_free_config", "get_default_professional_config", 
    "get_default_enterprise_config"
]