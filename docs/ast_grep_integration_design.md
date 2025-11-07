# AST-Grep Integration Design

## Overview
Integration of [ast-grep-essentials](https://github.com/coderabbitai/ast-grep-essentials) for structural code pattern analysis, organized into three distinct phases.

---

## System Architecture: Three-Phase Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRE-PROCESSING PHASE                             │
│  (Data Collection & Static Analysis)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  Graph Builder   │    │  Static Analysis │    │  AST-Grep Scanner│  │
│  │   (Layer 1)      │    │   (Linters)      │    │    (NEW)         │  │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘  │
│           │                       │                       │             │
│           │  Dependency Graph     │  Lint Results         │  Security   │
│           │  Risk Assessment      │  (flake8, eslint)     │  Findings   │
│           │                       │                       │             │
│           └───────────────────────┴───────────────────────┘             │
│                                   │                                     │
│                                   ▼                                     │
│                          ┌──────────────────┐                          │
│                          │   ContextData    │                          │
│                          │   (Aggregated)   │                          │
│                          └────────┬─────────┘                          │
└───────────────────────────────────┼──────────────────────────────────┘
                                    │
┌───────────────────────────────────┼──────────────────────────────────┐
│                         PROCESSING PHASE                              │
│  (AI-Driven Analysis & Enrichment)                                    │
├───────────────────────────────────┼──────────────────────────────────┤
│                                   ▼                                   │
│                    ┌──────────────────────────┐                       │
│                    │ ContextEngineeringAgent  │                       │
│                    │  - Formats ast-grep      │                       │
│                    │  - Correlates w/ graph   │                       │
│                    │  - Enriches w/ DeepWiki  │                       │
│                    └──────────┬───────────────┘                       │
│                               │                                       │
│                               │ EnrichedContext                       │
│                               ▼                                       │
│                    ┌──────────────────────────┐                       │
│                    │     ReviewAgent          │                       │
│                    │  - Complexity scoring    │                       │
│                    │  - Security risk weight  │                       │
│                    │  - Impact assessment     │                       │
│                    └──────────┬───────────────┘                       │
│                               │                                       │
│                               │ ReviewResponse                        │
│                               ▼                                       │
│                    ┌──────────────────────────┐                       │
│                    │  VerificationAgents      │                       │
│                    │  - Security specialist   │                       │
│                    │  - Performance check     │                       │
│                    │  - Style validation      │                       │
│                    └──────────┬───────────────┘                       │
│                               │                                       │
└───────────────────────────────┼───────────────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────────────┐
│                      POST-PROCESSING PHASE                             │
│  (Aggregation, Deduplication & Formatting)                             │
├───────────────────────────────┼───────────────────────────────────────┤
│                               ▼                                        │
│                    ┌──────────────────────────┐                        │
│                    │  SecurityAggregator      │                        │
│                    │   (NEW)                  │                        │
│                    │  - Dedupe findings       │                        │
│                    │  - Prioritize by risk    │                        │
│                    │  - Group by category     │                        │
│                    └──────────┬───────────────┘                        │
│                               │                                        │
│                               ▼                                        │
│                    ┌──────────────────────────┐                        │
│                    │  OutputFormatter         │                        │
│                    │  - GitHub comments       │                        │
│                    │  - Summary report        │                        │
│                    │  - Metrics tracking      │                        │
│                    └──────────┬───────────────┘                        │
│                               │                                        │
│                               ▼                                        │
│                         Final PR Review                                │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Pre-Processing (Data Collection)

### Components

#### 1.1 AST-Grep Scanner (NEW)
**Location**: `python/coderabbit_ai/analyzers/astgrep_scanner.py`

**Responsibilities**:
- Execute ast-grep against changed files
- Load rules from ast-grep-essentials repository
- Parse ast-grep output into structured format
- Classify findings by severity and category

**Input**:
```python
{
    "changed_files": ["src/auth.py", "src/api.py"],
    "project_root": "/path/to/repo",
    "rules_path": "/path/to/ast-grep-essentials"
}
```

**Output**:
```python
{
    "tool": "ast-grep",
    "findings": [
        {
            "rule_id": "python/security/sql-injection",
            "severity": "critical",
            "category": "security",
            "file": "src/api.py",
            "line": 42,
            "message": "Potential SQL injection vulnerability",
            "code_snippet": "cursor.execute(f\"SELECT * FROM users WHERE id={user_id}\")",
            "suggestion": "Use parameterized queries",
            "cwe_id": "CWE-89"
        }
    ],
    "stats": {
        "total_findings": 5,
        "by_severity": {"critical": 1, "high": 2, "medium": 2},
        "by_category": {"security": 3, "best-practice": 2}
    }
}
```

#### 1.2 Enhanced Static Analysis Aggregator
**Location**: `python/coderabbit_ai/analyzers/static_analysis_aggregator.py` (EXISTING - enhance)

**Enhancement**: Add ast-grep to existing linter pipeline

```python
def collect_static_analysis(
    changed_files: List[str],
    project_root: str,
    enable_astgrep: bool = True
) -> List[Dict[str, Any]]:
    """Collect all static analysis results."""
    results = []

    # Existing linters
    results.extend(run_flake8(changed_files))
    results.extend(run_eslint(changed_files))
    results.extend(run_pylint(changed_files))

    # NEW: AST-Grep
    if enable_astgrep:
        astgrep_scanner = AstGrepScanner(
            rules_repo="coderabbitai/ast-grep-essentials"
        )
        results.append(astgrep_scanner.scan(changed_files, project_root))

    return results
```

#### 1.3 Updated ContextData Model
**Location**: `python/coderabbit_ai/models.py` (EXISTING - enhance)

**Enhancement**: Add security-specific fields

```python
class SecurityFinding(BaseModel):
    """Structured security finding from ast-grep or other tools."""
    tool: str
    rule_id: str
    severity: str  # critical, high, medium, low
    category: str  # security, best-practice, performance
    file: str
    line: int
    message: str
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    cwe_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)

class ContextData(BaseModel):
    # ... existing fields ...
    static_analysis_results: List[Dict[str, Any]] = Field(default_factory=list)

    # NEW: Structured security findings
    security_findings: List[SecurityFinding] = Field(default_factory=list)
    security_summary: Optional[Dict[str, Any]] = None
```

---

## Phase 2: Processing (AI Analysis)

### Components

#### 2.1 Enhanced ContextEngineeringAgent
**Location**: `python/coderabbit_ai/agents/context_engineering.py` (EXISTING - enhance)

**New Method**: `_format_security_findings()`

```python
def _format_security_findings(self, findings: List[SecurityFinding]) -> str:
    """Format security findings for LLM consumption."""
    if not findings:
        return "No security findings from ast-grep."

    # Group by severity
    by_severity = defaultdict(list)
    for finding in findings:
        by_severity[finding.severity].append(finding)

    sections = []
    for severity in ["critical", "high", "medium", "low"]:
        items = by_severity.get(severity, [])
        if items:
            sections.append(f"\n{severity.upper()} SEVERITY ({len(items)} findings):")
            for finding in items:
                sections.append(f"  - {finding.file}:{finding.line}")
                sections.append(f"    Rule: {finding.rule_id}")
                sections.append(f"    Issue: {finding.message}")
                if finding.suggestion:
                    sections.append(f"    Fix: {finding.suggestion}")
                if finding.cwe_id:
                    sections.append(f"    CWE: {finding.cwe_id}")

    return "\n".join(sections)
```

**Enhanced forward()**: Include security context

```python
def forward(self, context_data: ContextData) -> ContextEngineeringResponse:
    # ... existing enrichment ...

    # NEW: Add security findings
    security_context = ""
    if context_data.security_findings:
        security_context = self._format_security_findings(
            context_data.security_findings
        )

    # Combine all context
    enriched_context = f"""
{hybrid_context_str}

{security_context}

{result.enriched_context}
    """

    return ContextEngineeringResponse(
        # ... existing fields ...
        metadata={
            # ... existing metadata ...
            "security_findings_count": len(context_data.security_findings),
            "critical_security_issues": sum(
                1 for f in context_data.security_findings
                if f.severity == "critical"
            )
        }
    )
```

#### 2.2 Enhanced ReviewAgent
**Location**: `python/coderabbit_ai/agents/review_agent.py` (EXISTING - enhance)

**New Method**: `_calculate_security_risk_weight()`

```python
def _calculate_security_risk_weight(
    self,
    context_response: ContextEngineeringResponse
) -> float:
    """Calculate security risk weight from ast-grep findings."""
    if not hasattr(context_response, 'metadata'):
        return 0.0

    critical = context_response.metadata.get('critical_security_issues', 0)
    total = context_response.metadata.get('security_findings_count', 0)

    if total == 0:
        return 0.0

    # Weight: critical issues heavily penalize
    if critical > 0:
        return 1.0  # Maximum risk
    elif total >= 5:
        return 0.8  # High risk (many issues)
    elif total >= 3:
        return 0.5  # Medium risk
    else:
        return 0.3  # Low risk
```

**Enhanced `_calculate_enhanced_complexity()`**:

```python
def _calculate_enhanced_complexity(
    self,
    code_changes: str,
    context_response: ContextEngineeringResponse
) -> float:
    # ... existing complexity calculations ...

    # NEW: Security risk component
    security_risk = self._calculate_security_risk_weight(context_response)

    # Weighted combination
    if graph_complexity > 0 or security_risk > 0:
        complexity_score = (
            size_complexity * 0.10 +          # Reduced
            structural_complexity * 0.20 +    # Reduced
            logic_complexity * 0.20 +         # Reduced
            context_complexity * 0.10 +       # Same
            risk_level * 0.05 +               # Same
            graph_complexity * 0.20 +         # Same
            security_risk * 0.15              # NEW: Security risk 15%
        )
    else:
        # Original weights without security
        complexity_score = (...)

    return min(1.0, complexity_score)
```

#### 2.3 Enhanced VerificationAgent (Security Specialist)
**Location**: `python/coderabbit_ai/agents/verification_agent.py` (EXISTING - enhance)

**Enhanced security specialization**:

```python
def _generate_specialization_context(self) -> str:
    contexts = {
        "security": """
            Focus on security vulnerabilities, authentication issues, authorization flaws,
            input validation, and data protection.

            **Enhanced with ast-grep findings:**
            - Structural vulnerabilities (SQL injection, XSS, CSRF)
            - Insecure cryptographic patterns
            - Authentication bypass patterns
            - Authorization logic flaws
            - Unsafe deserialization
            - Command injection risks

            **Correlation with graph analysis:**
            - High-risk files with security issues
            - Transitive impact of vulnerable components
            - Critical paths through insecure code

            **Validation tasks:**
            - Verify ast-grep findings accuracy (reduce false positives)
            - Suggest specific remediation for each CWE
            - Assess exploitability and business impact
        """,
        # ... other specializations ...
    }
    return contexts.get(self.specialization, "")
```

---

## Phase 3: Post-Processing (Aggregation & Output)

### Components

#### 3.1 SecurityAggregator (NEW)
**Location**: `python/coderabbit_ai/post_processing/security_aggregator.py`

**Responsibilities**:
- Deduplicate findings across multiple tools
- Prioritize by risk (severity × impact × exploitability)
- Group by category and file
- Generate executive summary

```python
class SecurityAggregator:
    """Aggregate and prioritize security findings from multiple sources."""

    def __init__(self):
        self.deduplication_cache = {}

    def aggregate(
        self,
        astgrep_findings: List[SecurityFinding],
        agent_feedback: List[VerificationAgentResponse],
        graph_context: Optional[GraphContextData] = None
    ) -> Dict[str, Any]:
        """Aggregate all security information."""

        # Step 1: Deduplicate
        unique_findings = self._deduplicate(astgrep_findings, agent_feedback)

        # Step 2: Prioritize using graph context
        prioritized = self._prioritize_with_graph(unique_findings, graph_context)

        # Step 3: Group by category
        grouped = self._group_by_category(prioritized)

        # Step 4: Generate summary
        summary = self._generate_summary(grouped)

        return {
            "findings": prioritized,
            "grouped": grouped,
            "summary": summary,
            "stats": self._calculate_stats(prioritized)
        }

    def _deduplicate(
        self,
        astgrep: List[SecurityFinding],
        agent_feedback: List[VerificationAgentResponse]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate findings."""
        unique = []
        seen_keys = set()

        for finding in astgrep:
            # Create unique key: file + line + rule
            key = f"{finding.file}:{finding.line}:{finding.rule_id}"

            if key not in seen_keys:
                # Check if agent validated this finding
                agent_validation = self._find_agent_validation(
                    finding, agent_feedback
                )

                unique.append({
                    "finding": finding,
                    "agent_validated": agent_validation is not None,
                    "agent_notes": agent_validation.get("notes") if agent_validation else None,
                    "false_positive_likelihood": agent_validation.get("false_positive_score", 0.0) if agent_validation else 0.0
                })
                seen_keys.add(key)

        return unique

    def _prioritize_with_graph(
        self,
        findings: List[Dict[str, Any]],
        graph_context: Optional[GraphContextData]
    ) -> List[Dict[str, Any]]:
        """Prioritize findings using graph impact analysis."""
        if not graph_context:
            # Simple prioritization: severity only
            return sorted(
                findings,
                key=lambda f: self._severity_to_int(f["finding"].severity),
                reverse=True
            )

        # Enhanced prioritization: severity × graph impact
        for item in findings:
            finding = item["finding"]

            # Check if file is critical in graph
            is_critical_file = any(
                cf["file"] == finding.file
                for cf in graph_context.critical_files
            )

            # Calculate priority score
            severity_score = self._severity_to_int(finding.severity)
            impact_multiplier = 2.0 if is_critical_file else 1.0
            false_positive_penalty = 1.0 - item["false_positive_likelihood"]

            item["priority_score"] = (
                severity_score *
                impact_multiplier *
                false_positive_penalty
            )

        return sorted(findings, key=lambda f: f["priority_score"], reverse=True)

    def _group_by_category(
        self,
        findings: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group findings by security category."""
        grouped = defaultdict(list)

        for item in findings:
            category = item["finding"].category
            grouped[category].append(item)

        return dict(grouped)

    def _generate_summary(self, grouped: Dict[str, List]) -> Dict[str, Any]:
        """Generate executive summary."""
        total = sum(len(items) for items in grouped.values())

        # Count by severity
        severity_counts = defaultdict(int)
        for items in grouped.values():
            for item in items:
                severity_counts[item["finding"].severity] += 1

        # Identify top risks
        all_findings = [item for items in grouped.values() for item in items]
        top_risks = sorted(all_findings, key=lambda f: f.get("priority_score", 0), reverse=True)[:5]

        return {
            "total_findings": total,
            "by_severity": dict(severity_counts),
            "by_category": {cat: len(items) for cat, items in grouped.items()},
            "top_5_risks": [
                {
                    "file": item["finding"].file,
                    "line": item["finding"].line,
                    "severity": item["finding"].severity,
                    "message": item["finding"].message,
                    "priority_score": item.get("priority_score", 0)
                }
                for item in top_risks
            ],
            "recommendation": self._get_recommendation(severity_counts)
        }

    def _get_recommendation(self, severity_counts: Dict[str, int]) -> str:
        """Generate recommendation based on findings."""
        critical = severity_counts.get("critical", 0)
        high = severity_counts.get("high", 0)

        if critical > 0:
            return "❌ BLOCK: Critical security vulnerabilities found. Must fix before merge."
        elif high >= 3:
            return "⚠️  CAUTION: Multiple high-severity issues. Strongly recommend review and fixes."
        elif high > 0:
            return "⚠️  WARNING: High-severity issues found. Review recommended."
        else:
            return "✅ APPROVE: No critical security issues detected."

    @staticmethod
    def _severity_to_int(severity: str) -> int:
        """Convert severity to numeric score."""
        mapping = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return mapping.get(severity.lower(), 0)
```

#### 3.2 Enhanced OutputFormatter
**Location**: `python/coderabbit_ai/output/formatter.py` (EXISTING - enhance)

**New Method**: `format_security_section()`

```python
def format_security_section(
    self,
    aggregated_security: Dict[str, Any]
) -> str:
    """Format security findings for PR comment."""
    summary = aggregated_security["summary"]

    output = ["## 🔒 Security Analysis\n"]

    # Recommendation badge
    recommendation = summary["recommendation"]
    output.append(f"{recommendation}\n")

    # Stats
    output.append(f"**Total Findings**: {summary['total_findings']}")
    output.append(f"**By Severity**: Critical: {summary['by_severity'].get('critical', 0)}, "
                  f"High: {summary['by_severity'].get('high', 0)}, "
                  f"Medium: {summary['by_severity'].get('medium', 0)}, "
                  f"Low: {summary['by_severity'].get('low', 0)}\n")

    # Top 5 risks
    if summary["top_5_risks"]:
        output.append("### 🚨 Top Priority Issues\n")
        for i, risk in enumerate(summary["top_5_risks"], 1):
            output.append(
                f"{i}. **{risk['severity'].upper()}** - "
                f"[{risk['file']}:{risk['line']}]({risk['file']}#L{risk['line']})\n"
                f"   {risk['message']}\n"
            )

    # Detailed findings by category
    grouped = aggregated_security["grouped"]
    if grouped:
        output.append("\n### 📋 Findings by Category\n")
        for category, items in grouped.items():
            output.append(f"<details>\n<summary>{category.title()} ({len(items)} issues)</summary>\n")
            for item in items[:10]:  # Limit to 10 per category
                finding = item["finding"]
                output.append(f"- **{finding.severity}** - {finding.file}:{finding.line}")
                output.append(f"  - {finding.message}")
                if finding.suggestion:
                    output.append(f"  - 💡 Suggested fix: {finding.suggestion}")
                if item["agent_validated"]:
                    output.append(f"  - ✅ Verified by AI security agent")
            output.append("</details>\n")

    return "\n".join(output)
```

---

## Configuration

### Environment Variables

```bash
# AST-Grep Configuration
ASTGREP_ENABLED=true
ASTGREP_RULES_REPO=coderabbitai/ast-grep-essentials
ASTGREP_RULES_PATH=/path/to/ast-grep-essentials
ASTGREP_CACHE_TTL=3600

# Security Thresholds
SECURITY_BLOCK_ON_CRITICAL=true
SECURITY_MAX_HIGH_SEVERITY=3
SECURITY_CONFIDENCE_THRESHOLD=0.7
```

### Config File Enhancement

`python/coderabbit_ai/config.py`:

```python
# AST-Grep settings
ASTGREP_ENABLED = os.getenv("ASTGREP_ENABLED", "true").lower() == "true"
ASTGREP_RULES_REPO = os.getenv("ASTGREP_RULES_REPO", "coderabbitai/ast-grep-essentials")
ASTGREP_RULES_PATH = os.getenv("ASTGREP_RULES_PATH", "/tmp/ast-grep-rules")
ASTGREP_CACHE_TTL = int(os.getenv("ASTGREP_CACHE_TTL", "3600"))

# Security thresholds
SECURITY_BLOCK_ON_CRITICAL = os.getenv("SECURITY_BLOCK_ON_CRITICAL", "true").lower() == "true"
SECURITY_MAX_HIGH_SEVERITY = int(os.getenv("SECURITY_MAX_HIGH_SEVERITY", "3"))
SECURITY_CONFIDENCE_THRESHOLD = float(os.getenv("SECURITY_CONFIDENCE_THRESHOLD", "0.7"))
```

---

## Data Flow Example

### Input: PR with SQL Injection

```python
# Changed file: src/api.py
def get_user(user_id):
    cursor.execute(f"SELECT * FROM users WHERE id={user_id}")
    return cursor.fetchone()
```

### Phase 1: Pre-Processing

**AstGrepScanner** detects:
```python
SecurityFinding(
    tool="ast-grep",
    rule_id="python/security/sql-injection",
    severity="critical",
    category="security",
    file="src/api.py",
    line=2,
    message="SQL injection vulnerability: user input directly in query",
    code_snippet='cursor.execute(f"SELECT * FROM users WHERE id={user_id}")',
    suggestion="Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))",
    cwe_id="CWE-89",
    confidence=0.95
)
```

**GraphBuilder** identifies:
```python
GraphContextData(
    risk_level="HIGH",
    critical_files=[{"file": "src/api.py", "importance": 0.85}],
    # api.py is used by 15 other files
)
```

### Phase 2: Processing

**ContextEngineeringAgent** enriches:
```
CRITICAL SEVERITY (1 finding):
  - src/api.py:2
    Rule: python/security/sql-injection
    Issue: SQL injection vulnerability: user input directly in query
    Fix: Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))
    CWE: CWE-89

GRAPH ANALYSIS:
  - src/api.py is a CRITICAL file (importance: 0.85)
  - Used by 15 other modules
  - Changes here have HIGH transitive impact
```

**ReviewAgent** calculates:
```python
complexity_score = (
    size_complexity * 0.10 +        # 0.02 (small change)
    structural_complexity * 0.20 +  # 0.04 (simple function)
    logic_complexity * 0.20 +       # 0.04 (no branches)
    context_complexity * 0.10 +     # 0.05 (used by 15 files)
    risk_level * 0.05 +             # 0.04 (high graph risk)
    graph_complexity * 0.20 +       # 0.16 (0.8 risk × 0.2 weight)
    security_risk * 0.15            # 0.15 (1.0 critical × 0.15 weight)
) = 0.50  # Medium-high complexity
```

**VerificationAgent (Security)** validates:
```
✅ Confirmed: SQL injection vulnerability
- User input `user_id` is unsanitized
- Passed directly to SQL query via f-string
- Exploitable: attacker can inject malicious SQL
- Impact: Complete database compromise
- Confidence: 95%
- False positive likelihood: 5%

Recommended fix:
```python
def get_user(user_id):
    # Use parameterized query to prevent SQL injection
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    return cursor.fetchone()
```
```

### Phase 3: Post-Processing

**SecurityAggregator** generates:
```python
{
    "summary": {
        "total_findings": 1,
        "by_severity": {"critical": 1},
        "by_category": {"security": 1},
        "top_5_risks": [
            {
                "file": "src/api.py",
                "line": 2,
                "severity": "critical",
                "message": "SQL injection vulnerability",
                "priority_score": 7.6  # 4 (critical) × 2.0 (critical file) × 0.95 (low FP)
            }
        ],
        "recommendation": "❌ BLOCK: Critical security vulnerabilities found. Must fix before merge."
    }
}
```

**OutputFormatter** produces:
```markdown
## 🔒 Security Analysis

❌ BLOCK: Critical security vulnerabilities found. Must fix before merge.

**Total Findings**: 1
**By Severity**: Critical: 1, High: 0, Medium: 0, Low: 0

### 🚨 Top Priority Issues

1. **CRITICAL** - [src/api.py:2](src/api.py#L2)
   SQL injection vulnerability: user input directly in query

   **Impact Analysis**:
   - File importance: 0.85 (CRITICAL)
   - Used by 15 other modules
   - Potential for full database compromise

   **Recommended Fix**:
   ```python
   cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
   ```

   **CWE-89**: Improper Neutralization of Special Elements used in an SQL Command

   ✅ Verified by AI security agent (95% confidence)
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_astgrep_scanner.py
def test_astgrep_detects_sql_injection()
def test_astgrep_rule_loading()
def test_astgrep_output_parsing()

# tests/test_security_aggregator.py
def test_deduplication()
def test_prioritization_with_graph()
def test_false_positive_filtering()
def test_executive_summary_generation()
```

### Integration Tests

```python
# tests/test_security_pipeline_e2e.py
def test_full_security_pipeline()
def test_critical_security_blocks_pr()
def test_security_findings_in_agent_responses()
```

---

## Performance Considerations

1. **Caching**: Cache ast-grep rules repository locally (TTL: 1 hour)
2. **Incremental Scanning**: Only scan changed files, not entire repo
3. **Parallel Execution**: Run ast-grep concurrently with other linters
4. **Rate Limiting**: Limit findings per PR (e.g., top 50) to avoid overwhelming output
5. **Async Processing**: Run security aggregation in background for large PRs

---

## Rollout Plan

### Phase 1: Foundation (Week 1)
- [ ] Implement AstGrepScanner
- [ ] Enhance ContextData with SecurityFinding model
- [ ] Update static analysis aggregator
- [ ] Write unit tests

### Phase 2: Integration (Week 2)
- [ ] Enhance ContextEngineeringAgent
- [ ] Update ReviewAgent complexity scoring
- [ ] Enhance VerificationAgent (security)
- [ ] Write integration tests

### Phase 3: Post-Processing (Week 3)
- [ ] Implement SecurityAggregator
- [ ] Enhance OutputFormatter
- [ ] Add configuration options
- [ ] Performance optimization

### Phase 4: Testing & Deployment (Week 4)
- [ ] End-to-end testing on real PRs
- [ ] Tune thresholds and weights
- [ ] Documentation
- [ ] Production deployment

---

## Success Metrics

1. **Detection Rate**: % of known vulnerabilities caught by ast-grep
2. **False Positive Rate**: Target < 10%
3. **Performance**: Pre-processing phase completes in < 30s for typical PR
4. **User Satisfaction**: Developers find recommendations actionable
5. **Security Improvement**: Reduction in vulnerabilities merged to main

---

## Next Steps

1. ✅ Design complete
2. ⏳ Get user approval
3. ⏳ Begin Phase 1 implementation
