"""Data models for CodeRabbit AI pipeline."""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
import dspy
from datetime import datetime


class Platform(str, Enum):
    """Supported platforms."""
    GITHUB = "github"
    GITLAB = "gitlab"
    AZURE_DEVOPS = "azure_devops"


class ChangeType(str, Enum):
    """Types of file changes."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


class CommentType(str, Enum):
    """Types of review comments."""
    SUGGESTION = "suggestion"
    ISSUE = "issue"
    PRAISE = "praise"


class Severity(str, Enum):
    """Severity levels for issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class User(BaseModel):
    """User model."""
    id: str
    username: str
    email: Optional[str] = None


class Repository(BaseModel):
    """Repository model."""
    id: str
    name: str
    owner: str
    platform: Platform
    clone_url: str
    default_branch: str


class FileChange(BaseModel):
    """File change model."""
    path: str
    change_type: ChangeType
    content: str
    diff: str
    language: str


class PullRequest(BaseModel):
    """Pull request model."""
    id: str
    number: int
    title: str
    description: str
    author: User
    base_branch: str
    head_branch: str
    files_changed: List[FileChange]


class ReviewComment(BaseModel):
    """Review comment model."""
    id: str
    file_path: str
    line_number: int
    comment_type: CommentType
    severity: Severity
    message: str
    suggested_fix: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=1.0)


class ReviewRules(BaseModel):
    """Review rules configuration."""
    enabled_checks: List[str]
    severity_thresholds: Dict[str, Severity]
    custom_rules: List[str]


class AISettings(BaseModel):
    """AI configuration settings."""
    primary_model: str
    fallback_models: List[str]
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(gt=0)


class Integration(BaseModel):
    """Platform integration configuration."""
    platform: Platform
    config: Dict[str, str]


class OrganizationConfig(BaseModel):
    """Organization configuration."""
    id: str
    name: str
    review_rules: ReviewRules
    ai_settings: AISettings
    integrations: List[Integration]


class SimilarPattern(BaseModel):
    """Similar code pattern from RAG."""
    file_path: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    content_snippet: str
    language: str


class RelatedIssue(BaseModel):
    """Related issue from RAG."""
    issue_id: str
    title: str
    description: str
    similarity_score: float = Field(ge=0.0, le=1.0)


class BestPractice(BaseModel):
    """Best practice recommendation from RAG."""
    practice_id: str
    description: str
    category: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class RagContextData(BaseModel):
    """RAG context data for enhanced code review."""
    similar_patterns: List[SimilarPattern] = Field(default_factory=list)
    related_issues: List[RelatedIssue] = Field(default_factory=list)
    best_practices: List[BestPractice] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    """Review request model."""
    repository: Repository
    pull_request: PullRequest
    config: OrganizationConfig
    rag_context: Optional[RagContextData] = None


class ReviewMetrics(BaseModel):
    """Review metrics model."""
    analysis_time_ms: int
    files_analyzed: int
    issues_found: int
    ai_cost: float


class ReviewResponse(BaseModel):
    """Review response model."""
    review_id: str
    status: str
    comments: List[ReviewComment]
    metrics: ReviewMetrics


class ContextData(BaseModel):
    """Context data for AI agents."""
    repo_structure: str
    code_changes: str
    historical_data: str
    static_analysis_results: List[Dict[str, Any]]
    code_relationships: Optional[str] = None
    rag_context: Optional[RagContextData] = None


class AgentResponse(BaseModel):
    """Base response from AI agents."""
    agent_id: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    processing_time_ms: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextEngineeringResponse(AgentResponse):
    """Response from Context Engineering Agent."""
    enriched_context: str
    code_relationships: str
    relevant_patterns: str


class ReviewAgentResponse(AgentResponse):
    """Response from Review Agent."""
    review_findings: str
    confidence_scores: Dict[str, float]
    suggested_improvements: List[str]


class VerificationAgentResponse(AgentResponse):
    """Response from Verification Agent."""
    filtered_findings: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    specialization: str


# DSPy Signatures for Multi-Agent Pipeline
class ContextEngineeringSignature(dspy.Signature):
    """Comprehensive context gathering for code review with 40+ static analysis tools."""

    # Input fields
    repo_structure: str = dspy.InputField(
        desc="Complete repository structure with file tree, dependencies, and metadata"
    )
    code_changes: str = dspy.InputField(
        desc="Detailed PR changes with diffs, file paths, and change types"
    )
    historical_data: str = dspy.InputField(
        desc="Historical PR data, past issues, and chat conversation learnings"
    )
    static_analysis_results: str = dspy.InputField(
        desc="Aggregated results from 40+ linters and SAST tools (ESLint, Clippy, Bandit, etc.)"
    )
    ast_features: str = dspy.InputField(
        desc="AST-based code features and structural analysis"
    )
    rag_context: str = dspy.InputField(
        desc="RAG-retrieved context: similar code patterns, related issues, historical bugs, and best practices from vector database"
    )

    # Output fields
    enriched_context: str = dspy.OutputField(
        desc="Comprehensive analysis context with code understanding and relationships"
    )
    code_relationships: str = dspy.OutputField(
        desc="AST-based code relationships, dependencies, and impact analysis"
    )
    relevant_patterns: str = dspy.OutputField(
        desc="Historical patterns, similar issues, and learned best practices"
    )
    risk_assessment: str = dspy.OutputField(
        desc="Risk assessment based on change complexity and historical data"
    )


class ReviewAgentSignature(dspy.Signature):
    """Primary code review analysis with multi-model routing capability."""
    
    # Input fields
    enriched_context: str = dspy.InputField(
        desc="Enriched context from Context Engineering Agent"
    )
    code_changes: str = dspy.InputField(
        desc="Code changes to review with full context"
    )
    organization_config: str = dspy.InputField(
        desc="Organization-specific rules, preferences, and configuration"
    )
    model_selection_hint: str = dspy.InputField(
        desc="Hint for optimal model selection based on complexity and budget"
    )
    
    # Output fields
    review_findings: str = dspy.OutputField(
        desc="Comprehensive review findings with detailed analysis"
    )
    confidence_scores: str = dspy.OutputField(
        desc="Confidence scores for each finding and overall review quality"
    )
    suggested_improvements: str = dspy.OutputField(
        desc="Actionable improvement suggestions with code examples"
    )
    priority_ranking: str = dspy.OutputField(
        desc="Priority ranking of issues from most critical to least important"
    )


class VerificationAgentSignature(dspy.Signature):
    """Specialized verification for specific code review aspects."""
    
    # Input fields
    review_findings: str = dspy.InputField(
        desc="Review findings from the primary Review Agent"
    )
    specialization_context: str = dspy.InputField(
        desc="Domain-specific context for specialized verification (security, performance, style, etc.)"
    )
    organization_config: str = dspy.InputField(
        desc="Organization-specific rules and configuration for this specialization"
    )
    code_context: str = dspy.InputField(
        desc="Relevant code context and relationships for verification"
    )
    
    # Output fields
    filtered_findings: str = dspy.OutputField(
        desc="Verified and filtered findings specific to this agent's specialization"
    )
    relevance_score: str = dspy.OutputField(
        desc="Relevance score (0.0-1.0) indicating confidence in findings"
    )
    additional_insights: str = dspy.OutputField(
        desc="Additional insights or recommendations from specialized analysis"
    )
    false_positive_flags: str = dspy.OutputField(
        desc="Flags for potential false positives that should be filtered out"
    )


class ConsensusBuilderSignature(dspy.Signature):
    """Build consensus from multiple verification agents."""

    # Input fields
    primary_review: str = dspy.InputField(
        desc="Primary review findings from the Review Agent"
    )
    verification_results: str = dspy.InputField(
        desc="Aggregated results from all verification agents"
    )
    organization_config: str = dspy.InputField(
        desc="Organization configuration for filtering and consensus rules"
    )
    confidence_thresholds: str = dspy.InputField(
        desc="Confidence thresholds for including findings in final output"
    )

    # Output fields
    final_comments: str = dspy.OutputField(
        desc="Final filtered and ranked comments for the code review"
    )
    consensus_score: str = dspy.OutputField(
        desc="Overall consensus score indicating agreement between agents"
    )
    quality_metrics: str = dspy.OutputField(
        desc="Quality metrics for the review including coverage and confidence"
    )


class SummarizationSignature(dspy.Signature):
    """Generate comprehensive PR summary with high-level overview and technical walkthrough."""

    # Input fields
    pr_metadata: str = dspy.InputField(
        desc="PR metadata including title, description, author, branch names, and linked issues"
    )
    file_changes: str = dspy.InputField(
        desc="Complete list of changed files with change types (added/modified/deleted) and language"
    )
    code_diff_stats: str = dspy.InputField(
        desc="Diff statistics: lines added/removed, files changed, complexity metrics"
    )
    static_analysis_summary: str = dspy.InputField(
        desc="Aggregated results from static analysis tools and linters"
    )
    historical_context: str = dspy.InputField(
        desc="Related PRs, similar changes, and relevant project history"
    )

    # Output fields
    high_level_summary: str = dspy.OutputField(
        desc="Executive summary (2-3 sentences) explaining what this PR does and why"
    )
    technical_walkthrough: str = dspy.OutputField(
        desc="Technical walkthrough with structured sections: changes by component, key modifications, impact analysis"
    )
    change_categories: str = dspy.OutputField(
        desc="Categorized changes (feature/bugfix/refactor/docs/tests) with file counts"
    )
    risk_assessment: str = dspy.OutputField(
        desc="Risk level (low/medium/high) with justification based on change scope and complexity"
    )
    affected_components: str = dspy.OutputField(
        desc="List of affected system components/modules with impact description"
    )
    testing_recommendations: str = dspy.OutputField(
        desc="Specific areas requiring testing focus based on changes"
    )


class SecurityAnalysisSignature(dspy.Signature):
    """Deep security analysis for vulnerabilities, threats, and security best practices."""

    # Input fields
    code_changes: str = dspy.InputField(
        desc="Code changes with focus on security-sensitive areas (auth, data handling, encryption)"
    )
    security_scan_results: str = dspy.InputField(
        desc="Results from SAST tools like Bandit, Semgrep, CodeQL, and security linters"
    )
    dependency_analysis: str = dspy.InputField(
        desc="Dependency vulnerability scan results from tools like Snyk, OWASP Dependency-Check"
    )
    threat_model_context: str = dspy.InputField(
        desc="Application threat model and security requirements"
    )

    # Output fields
    security_vulnerabilities: str = dspy.OutputField(
        desc="Detailed security vulnerabilities with severity levels (Critical, High, Medium, Low)"
    )
    exploit_scenarios: str = dspy.OutputField(
        desc="Potential exploit scenarios and attack vectors for identified vulnerabilities"
    )
    remediation_steps: str = dspy.OutputField(
        desc="Step-by-step remediation guidance with secure code examples"
    )
    security_score: str = dspy.OutputField(
        desc="Overall security score (0-100) based on vulnerability severity and coverage"
    )


class PerformanceAnalysisSignature(dspy.Signature):
    """Performance analysis for bottlenecks, optimization opportunities, and scalability."""

    # Input fields
    code_changes: str = dspy.InputField(
        desc="Code changes with focus on performance-critical sections (loops, DB queries, API calls)"
    )
    profiling_data: str = dspy.InputField(
        desc="Profiling results, benchmarks, and performance metrics if available"
    )
    complexity_analysis: str = dspy.InputField(
        desc="Algorithmic complexity analysis from AST and static analysis tools"
    )
    resource_constraints: str = dspy.InputField(
        desc="System resource constraints and performance requirements"
    )

    # Output fields
    performance_issues: str = dspy.OutputField(
        desc="Identified performance bottlenecks with time/space complexity analysis"
    )
    optimization_opportunities: str = dspy.OutputField(
        desc="Concrete optimization suggestions with before/after code examples"
    )
    scalability_concerns: str = dspy.OutputField(
        desc="Scalability concerns and recommendations for handling increased load"
    )
    performance_score: str = dspy.OutputField(
        desc="Performance score (0-100) based on complexity, efficiency, and best practices"
    )


class CodeQualitySignature(dspy.Signature):
    """Code quality assessment covering maintainability, readability, and best practices."""

    # Input fields
    code_changes: str = dspy.InputField(
        desc="Code changes to assess for quality, style, and maintainability"
    )
    linter_results: str = dspy.InputField(
        desc="Linter results from ESLint, Pylint, RuboCop, Clippy, etc."
    )
    complexity_metrics: str = dspy.InputField(
        desc="Code complexity metrics (cyclomatic complexity, cognitive complexity, nesting depth)"
    )
    style_guide: str = dspy.InputField(
        desc="Project-specific style guide and coding standards"
    )

    # Output fields
    quality_issues: str = dspy.OutputField(
        desc="Code quality issues including smells, anti-patterns, and style violations"
    )
    refactoring_suggestions: str = dspy.OutputField(
        desc="Refactoring recommendations with improved code examples"
    )
    maintainability_assessment: str = dspy.OutputField(
        desc="Maintainability assessment with long-term sustainability concerns"
    )
    quality_score: str = dspy.OutputField(
        desc="Overall quality score (0-100) based on maintainability and best practices"
    )


class DocumentationReviewSignature(dspy.Signature):
    """Documentation quality review for code comments, API docs, and README updates."""

    # Input fields
    code_changes: str = dspy.InputField(
        desc="Code changes with inline comments, docstrings, and documentation files"
    )
    api_surface_changes: str = dspy.InputField(
        desc="Public API changes that require documentation"
    )
    existing_documentation: str = dspy.InputField(
        desc="Existing documentation context (README, API docs, user guides)"
    )
    documentation_standards: str = dspy.InputField(
        desc="Documentation standards and requirements for the project"
    )

    # Output fields
    documentation_gaps: str = dspy.OutputField(
        desc="Missing or insufficient documentation with specific locations"
    )
    documentation_improvements: str = dspy.OutputField(
        desc="Suggestions for improving clarity, completeness, and accuracy of docs"
    )
    example_documentation: str = dspy.OutputField(
        desc="Example documentation snippets for complex or poorly documented code"
    )
    documentation_score: str = dspy.OutputField(
        desc="Documentation completeness score (0-100) based on coverage and quality"
    )


class TestCoverageSignature(dspy.Signature):
    """Test coverage analysis and testing strategy recommendations."""

    # Input fields
    code_changes: str = dspy.InputField(
        desc="Code changes that require test coverage"
    )
    existing_tests: str = dspy.InputField(
        desc="Existing test suite and coverage reports"
    )
    coverage_metrics: str = dspy.InputField(
        desc="Coverage metrics (line coverage, branch coverage, mutation score)"
    )
    critical_paths: str = dspy.InputField(
        desc="Critical code paths that must be tested"
    )

    # Output fields
    coverage_gaps: str = dspy.OutputField(
        desc="Untested or under-tested code with specific functions/branches"
    )
    test_recommendations: str = dspy.OutputField(
        desc="Recommended test cases with example test code"
    )
    edge_cases: str = dspy.OutputField(
        desc="Important edge cases and boundary conditions to test"
    )
    coverage_score: str = dspy.OutputField(
        desc="Test coverage adequacy score (0-100) based on coverage and quality"
    )


class ArchitectureReviewSignature(dspy.Signature):
    """Architecture and design pattern analysis for system-level concerns."""

    # Input fields
    code_changes: str = dspy.InputField(
        desc="Code changes affecting system architecture or design patterns"
    )
    system_architecture: str = dspy.InputField(
        desc="Current system architecture and design documentation"
    )
    design_patterns: str = dspy.InputField(
        desc="Identified design patterns and architectural patterns in use"
    )
    architectural_requirements: str = dspy.InputField(
        desc="Architectural requirements and constraints"
    )

    # Output fields
    architectural_issues: str = dspy.OutputField(
        desc="Architectural anti-patterns, violations of principles (SOLID, DRY, etc.)"
    )
    design_recommendations: str = dspy.OutputField(
        desc="Better design patterns and architectural approaches"
    )
    impact_analysis: str = dspy.OutputField(
        desc="Impact analysis of changes on overall system architecture"
    )
    architecture_score: str = dspy.OutputField(
        desc="Architectural quality score (0-100) based on principles and patterns"
    )


class APIDesignSignature(dspy.Signature):
    """API design review for REST endpoints, GraphQL schemas, and public interfaces."""

    # Input fields
    api_changes: str = dspy.InputField(
        desc="API changes including endpoints, schemas, request/response formats"
    )
    api_specification: str = dspy.InputField(
        desc="API specification (OpenAPI, GraphQL schema, protobuf definitions)"
    )
    compatibility_requirements: str = dspy.InputField(
        desc="Backward compatibility requirements and versioning strategy"
    )
    api_standards: str = dspy.InputField(
        desc="API design standards and best practices for the organization"
    )

    # Output fields
    api_design_issues: str = dspy.OutputField(
        desc="API design problems (inconsistent naming, poor error handling, breaking changes)"
    )
    consistency_suggestions: str = dspy.OutputField(
        desc="Suggestions for improving API consistency and developer experience"
    )
    breaking_changes: str = dspy.OutputField(
        desc="Identified breaking changes with migration strategies"
    )
    api_quality_score: str = dspy.OutputField(
        desc="API design quality score (0-100) based on best practices and consistency"
    )


class DependencyAnalysisSignature(dspy.Signature):
    """Dependency analysis for package updates, vulnerabilities, and compatibility."""

    # Input fields
    dependency_changes: str = dspy.InputField(
        desc="Changes to dependencies (additions, updates, removals)"
    )
    dependency_graph: str = dspy.InputField(
        desc="Full dependency graph with versions and transitive dependencies"
    )
    vulnerability_scan: str = dspy.InputField(
        desc="Vulnerability scan results for all dependencies"
    )
    compatibility_matrix: str = dspy.InputField(
        desc="Compatibility requirements and version constraints"
    )

    # Output fields
    dependency_risks: str = dspy.OutputField(
        desc="Risks from new dependencies (vulnerabilities, license issues, unmaintained packages)"
    )
    update_recommendations: str = dspy.OutputField(
        desc="Recommended dependency updates for security and compatibility"
    )
    conflict_resolutions: str = dspy.OutputField(
        desc="Dependency conflict resolutions and version pinning strategies"
    )
    dependency_health_score: str = dspy.OutputField(
        desc="Dependency health score (0-100) based on security and maintainability"
    )


# Data Transfer Objects for Rust-Python Communication
class RustPythonMessage(BaseModel):
    """Base message for Rust-Python communication."""
    message_id: str
    timestamp: datetime
    message_type: str


class CodeAnalysisRequest(RustPythonMessage):
    """Request for code analysis from Rust to Python."""
    repository: Repository
    pull_request: PullRequest
    config: OrganizationConfig
    static_analysis_results: List[Dict[str, Any]]
    ast_features: Dict[str, Any]


class CodeAnalysisResponse(RustPythonMessage):
    """Response from Python AI pipeline to Rust."""
    review_id: str
    comments: List[ReviewComment]
    metrics: ReviewMetrics
    processing_details: Dict[str, Any]


class AgentExecutionContext(BaseModel):
    """Execution context for AI agents."""
    request_id: str
    organization_id: str
    repository_id: str
    pr_number: int
    execution_config: Dict[str, Any]
    budget_limits: Dict[str, float]
    timeout_seconds: int = 300


class ModelSelectionConfig(BaseModel):
    """Configuration for intelligent model selection."""
    primary_model: str = "claude-3-5-sonnet"
    fallback_models: List[str] = ["gpt-4", "gpt-3.5-turbo"]
    cost_budget: float = 1.0  # USD
    quality_threshold: float = 0.8
    latency_requirement_ms: int = 5000


class DSPyOptimizationConfig(BaseModel):
    """Configuration for DSPy optimization."""
    optimization_metric: str = "review_quality"
    num_candidates: int = 50
    init_temperature: float = 0.7
    max_iterations: int = 100
    evaluation_dataset_size: int = 200


class CacheConfig(BaseModel):
    """Configuration for caching strategies."""
    enable_prompt_caching: bool = True
    enable_result_caching: bool = True
    cache_ttl_seconds: int = 3600
    max_cache_size_mb: int = 1024


class PipelineConfig(BaseModel):
    """Complete pipeline configuration."""
    model_selection: ModelSelectionConfig
    optimization: DSPyOptimizationConfig
    caching: CacheConfig
    max_verification_agents: int = 10
    parallel_processing: bool = True
    enable_consensus_building: bool = True


# Validation functions
def validate_confidence_score(score: float) -> float:
    """Validate confidence score is between 0.0 and 1.0."""
    if not 0.0 <= score <= 1.0:
        raise ValueError("Confidence score must be between 0.0 and 1.0")
    return score


def validate_severity_level(severity: str) -> str:
    """Validate severity level is valid."""
    valid_levels = [s.value for s in Severity]
    if severity not in valid_levels:
        raise ValueError(f"Severity must be one of: {valid_levels}")
    return severity


# Model validation
ReviewComment.model_validate = validator('confidence_score')(validate_confidence_score)
AgentResponse.model_validate = validator('confidence_score')(validate_confidence_score)
VerificationAgentResponse.model_validate = validator('relevance_score')(validate_confidence_score)


# Export all models for easy importing
__all__ = [
    # Enums
    "Platform", "ChangeType", "CommentType", "Severity",

    # Core Models
    "User", "Repository", "FileChange", "PullRequest", "ReviewComment",
    "ReviewRules", "AISettings", "Integration", "OrganizationConfig",
    "ReviewRequest", "ReviewMetrics", "ReviewResponse",

    # RAG Models
    "SimilarPattern", "RelatedIssue", "BestPractice", "RagContextData",

    # Agent Models
    "ContextData", "AgentResponse", "ContextEngineeringResponse",
    "ReviewAgentResponse", "VerificationAgentResponse",

    # DSPy Signatures
    "ContextEngineeringSignature", "ReviewAgentSignature",
    "VerificationAgentSignature", "ConsensusBuilderSignature",

    # Communication Models
    "RustPythonMessage", "CodeAnalysisRequest", "CodeAnalysisResponse",
    "AgentExecutionContext",

    # Configuration Models
    "ModelSelectionConfig", "DSPyOptimizationConfig", "CacheConfig",
    "PipelineConfig",

    # Validation Functions
    "validate_confidence_score", "validate_severity_level"
]