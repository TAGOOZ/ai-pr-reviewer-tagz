# System Architecture: Three-Phase Component Mapping

## Complete System Component Breakdown

---

## 🔵 PHASE 1: PRE-PROCESSING (Data Collection & Static Analysis)

**Purpose**: Collect all raw data, perform static analysis, build dependency graphs, and prepare structured inputs for AI agents.

### 1.1 Data Collection Components

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **PRInputCollector** | `python/coderabbit_ai/collectors/pr_input_collector.py` | Fetch PR metadata from GitHub API | ✅ Existing |
| **CodeChangeParser** | `python/coderabbit_ai/parsers/code_change_parser.py` | Parse diff files, extract hunks | ✅ Existing |
| **RepoStructureAnalyzer** | `python/coderabbit_ai/analyzers/repo_structure.py` | Analyze repo directory structure | ✅ Existing |
| **HistoricalDataFetcher** | `python/coderabbit_ai/collectors/historical_data.py` | Fetch commit history, past reviews | ✅ Existing |

### 1.2 Static Analysis Components

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **StaticAnalysisAggregator** | `python/coderabbit_ai/analyzers/static_analysis_aggregator.py` | Orchestrate all linters | ✅ Existing |
| **Flake8Runner** | `python/coderabbit_ai/analyzers/linters/flake8_runner.py` | Run flake8 on Python files | ✅ Existing |
| **ESLintRunner** | `python/coderabbit_ai/analyzers/linters/eslint_runner.py` | Run eslint on JS/TS files | ✅ Existing |
| **PyLintRunner** | `python/coderabbit_ai/analyzers/linters/pylint_runner.py` | Run pylint on Python files | ✅ Existing |
| **AstGrepScanner** | `python/coderabbit_ai/analyzers/astgrep_scanner.py` | AST-based security scanning | 🆕 Planned |

### 1.3 Graph & Dependency Analysis (Layer 1)

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **DependencyGraphBuilder** | `python/coderabbit_ai/integrations/graph/dependency_graph.py` | Build NetworkX dependency graph | ✅ Existing |
| **PythonGraphBuilder** | `python/coderabbit_ai/integrations/graph/builders/python_builder.py` | Parse Python imports/dependencies | ✅ Existing |
| **JavaScriptGraphBuilder** | `python/coderabbit_ai/integrations/graph/builders/javascript_builder.py` | Parse JS/TS imports/dependencies | ✅ Existing |
| **GoGraphBuilder** | `python/coderabbit_ai/integrations/graph/builders/go_builder.py` | Parse Go imports/dependencies | ✅ Existing |
| **ImpactAnalyzer** | `python/coderabbit_ai/integrations/graph/impact_analyzer.py` | Calculate blast radius of changes | ✅ Existing |
| **RiskAssessor** | `python/coderabbit_ai/integrations/graph/risk_assessor.py` | Assess risk level (LOW/MEDIUM/HIGH/CRITICAL) | ✅ Existing |
| **GraphCache** | `python/coderabbit_ai/integrations/graph/cache.py` | Cache dependency graphs (TTL-based) | ✅ Existing |

### 1.4 Semantic Documentation (Layer 2)

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **DeepWikiClient** | `python/coderabbit_ai/integrations/deepwiki_client.py` | MCP client for DeepWiki server | ✅ Existing |
| **DeepWikiQueryBuilder** | `python/coderabbit_ai/integrations/deepwiki_client.py` | Build queries for architectural context | ✅ Existing |
| **DeepWikiResponseParser** | `python/coderabbit_ai/integrations/deepwiki_client.py` | Parse DeepWiki responses | ✅ Existing |

### 1.5 Hybrid Context Integration

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **HybridContextProvider** | `python/coderabbit_ai/integrations/hybrid_context_provider.py` | Orchestrate Graph + DeepWiki enrichment | ✅ Existing |
| **ContextAdapter** | `python/coderabbit_ai/integrations/context_adapter.py` | Convert HybridContext to Pydantic models | ✅ Existing |

### 1.6 Data Models (Pre-Processing)

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **ContextData** | `python/coderabbit_ai/models.py` | Container for all collected data | ✅ Existing |
| **GraphContextData** | `python/coderabbit_ai/models.py` | Structured graph analysis results | ✅ Existing |
| **DeepWikiContextData** | `python/coderabbit_ai/models.py` | Structured DeepWiki results | ✅ Existing |
| **HybridContextData** | `python/coderabbit_ai/models.py` | Combined graph + DeepWiki data | ✅ Existing |
| **SecurityFinding** | `python/coderabbit_ai/models.py` | Structured security findings | 🆕 Planned |

### 1.7 Configuration & Utilities

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **Config** | `python/coderabbit_ai/config.py` | Environment variables, settings | ✅ Existing |
| **ConfigModels** | `python/coderabbit_ai/config_models.py` | Organization-specific config schemas | ✅ Existing |
| **Logger** | `python/coderabbit_ai/utils/logger.py` | Centralized logging | ✅ Existing |
| **FileUtils** | `python/coderabbit_ai/utils/file_utils.py` | File I/O helpers | ✅ Existing |

---

## 🟢 PHASE 2: PROCESSING (AI-Driven Analysis & Enrichment)

**Purpose**: AI agents analyze collected data, generate insights, score complexity, identify issues, and provide recommendations.

### 2.1 Core AI Agents

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **ContextEngineeringAgent** | `python/coderabbit_ai/agents/context_engineering.py` | Enrich context with graph/DeepWiki/security | ✅ Existing + 🔧 Enhanced |
| **ReviewAgent** | `python/coderabbit_ai/agents/review_agent.py` | Perform code review, score complexity | ✅ Existing + 🔧 Enhanced |
| **VerificationAgent** | `python/coderabbit_ai/agents/verification_agent.py` | Specialized verification (security/perf/style) | ✅ Existing + 🔧 Enhanced |

### 2.2 Agent Components (ContextEngineeringAgent)

| Component | Method/Function | Responsibility | Status |
|-----------|-----------------|----------------|--------|
| **DSPy Context Generator** | `context_generator` (DSPy module) | LLM-powered context enrichment | ✅ Existing |
| **Static Analysis Formatter** | `_format_static_analysis()` | Format linter results for LLM | ✅ Existing |
| **Security Findings Formatter** | `_format_security_findings()` | Format ast-grep results for LLM | 🆕 Planned |
| **Hybrid Context Enricher** | `_enrich_with_hybrid_context()` | Call HybridContextProvider | ✅ Existing |
| **Changed Files Extractor** | `_extract_changed_files()` | Extract file list from diff | ✅ Existing |
| **Confidence Calculator** | `forward()` logic | Calculate context quality score | ✅ Existing |

### 2.3 Agent Components (ReviewAgent)

| Component | Method/Function | Responsibility | Status |
|-----------|-----------------|----------------|--------|
| **DSPy Reviewer** | `reviewer` (DSPy module) | LLM-powered code review | ✅ Existing |
| **Complexity Calculator** | `_calculate_enhanced_complexity()` | Multi-factor complexity scoring | ✅ Existing + 🔧 Enhanced |
| **Size Complexity** | Sub-calculation in complexity | Lines changed, files touched | ✅ Existing |
| **Structural Complexity** | Sub-calculation in complexity | Nesting, functions, classes | ✅ Existing |
| **Logic Complexity** | Sub-calculation in complexity | Branches, loops, conditionals | ✅ Existing |
| **Context Complexity** | Sub-calculation in complexity | Dependencies, imports | ✅ Existing |
| **Graph Complexity** | Sub-calculation in complexity | Graph risk level (20% weight) | ✅ Existing |
| **Security Risk Weight** | `_calculate_security_risk_weight()` | ast-grep findings (15% weight) | 🆕 Planned |
| **Language Detector** | `_detect_primary_language()` | Identify dominant language | ✅ Existing |
| **Model Router** | `model_router` | Route to appropriate LLM | ✅ Existing |

### 2.4 Agent Components (VerificationAgent)

| Component | Method/Function | Responsibility | Status |
|-----------|-----------------|----------------|--------|
| **DSPy Verifier** | `verifier` (DSPy module) | LLM-powered specialized verification | ✅ Existing |
| **Specialization Context Generator** | `_generate_specialization_context()` | Context for security/perf/style/etc | ✅ Existing + 🔧 Enhanced |
| **Security Specialist** | Specialization: "security" | Validate security findings, suggest fixes | ✅ Existing + 🔧 Enhanced |
| **Performance Specialist** | Specialization: "performance" | Identify bottlenecks, optimization | ✅ Existing |
| **Style Specialist** | Specialization: "style" | Code formatting, conventions | ✅ Existing |
| **Logic Specialist** | Specialization: "logic" | Business logic validation | ✅ Existing |
| **Testing Specialist** | Specialization: "testing" | Test coverage, quality | ✅ Existing |
| **Documentation Specialist** | Specialization: "documentation" | Docstring, comment quality | ✅ Existing |
| **Accessibility Specialist** | Specialization: "accessibility" | UI accessibility checks | ✅ Existing |
| **Maintainability Specialist** | Specialization: "maintainability" | Technical debt, refactoring | ✅ Existing |
| **Architecture Specialist** | Specialization: "architecture" | Design patterns, structure | ✅ Existing |
| **Dependencies Specialist** | Specialization: "dependencies" | Package management, versions | ✅ Existing |
| **Requirements Specialist** | Specialization: "requirements_validation" | Requirements compliance | ✅ Existing |

### 2.5 Agent Orchestration

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **AgentOrchestrator** | `python/coderabbit_ai/orchestrator.py` | Coordinate agent execution flow | ✅ Existing |
| **Sequential Executor** | `orchestrator.py` | Execute agents in sequence | ✅ Existing |
| **Parallel Executor** | `orchestrator.py` (if implemented) | Execute verification agents in parallel | 🔧 Optional |

### 2.6 LLM Integration

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **DSPy Framework** | `dspy` (external library) | LLM orchestration framework | ✅ Existing |
| **ModelRouter** | `python/coderabbit_ai/model_router.py` | Route to Claude/GPT/Gemini | ✅ Existing |
| **PromptTemplates** | Embedded in DSPy signatures | Structured prompts for agents | ✅ Existing |
| **LLM Response Parser** | DSPy automatic parsing | Extract structured data from LLM | ✅ Existing |

### 2.7 Data Models (Processing)

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **ContextEngineeringResponse** | `python/coderabbit_ai/models.py` | Output from ContextEngineeringAgent | ✅ Existing |
| **ReviewAgentResponse** | `python/coderabbit_ai/models.py` | Output from ReviewAgent | ✅ Existing |
| **VerificationAgentResponse** | `python/coderabbit_ai/models.py` | Output from VerificationAgent | ✅ Existing |
| **ReviewComment** | `python/coderabbit_ai/models.py` | Individual review comment | ✅ Existing |
| **AgentResponse** | `python/coderabbit_ai/models.py` | Base agent response | ✅ Existing |

---

## 🟡 PHASE 3: POST-PROCESSING (Aggregation, Deduplication & Output)

**Purpose**: Aggregate agent outputs, deduplicate findings, prioritize issues, format for user consumption, and deliver final review.

### 3.1 Aggregation Components

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **ResponseAggregator** | `python/coderabbit_ai/post_processing/aggregator.py` | Combine all agent responses | ✅ Existing |
| **CommentDeduplicator** | `python/coderabbit_ai/post_processing/deduplicator.py` | Remove duplicate comments | ✅ Existing |
| **SecurityAggregator** | `python/coderabbit_ai/post_processing/security_aggregator.py` | Aggregate security findings | 🆕 Planned |
| **PriorityScorer** | `python/coderabbit_ai/post_processing/priority_scorer.py` | Score and rank comments by importance | ✅ Existing |

### 3.2 Deduplication & Filtering

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **SemanticDeduplicator** | `deduplicator.py` | Use embeddings to detect similar comments | ✅ Existing |
| **LocationDeduplicator** | `deduplicator.py` | Dedupe by file + line | ✅ Existing |
| **ConfidenceFilter** | `post_processing/filters.py` | Filter low-confidence findings | ✅ Existing |
| **FalsePositiveFilter** | `post_processing/filters.py` | Remove likely false positives | 🔧 Optional |

### 3.3 Prioritization & Ranking

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **SeverityRanker** | `priority_scorer.py` | Rank by severity (critical > high > medium) | ✅ Existing |
| **ImpactRanker** | `priority_scorer.py` | Rank by blast radius (graph context) | ✅ Existing |
| **ConfidenceRanker** | `priority_scorer.py` | Rank by agent confidence | ✅ Existing |
| **CompositeRanker** | `priority_scorer.py` | Combined ranking algorithm | ✅ Existing |

### 3.4 Output Formatting

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **OutputFormatter** | `python/coderabbit_ai/output/formatter.py` | Format final PR review | ✅ Existing |
| **MarkdownFormatter** | `formatter.py` | Generate markdown for GitHub | ✅ Existing |
| **SummaryGenerator** | `formatter.py` | Executive summary section | ✅ Existing |
| **CommentFormatter** | `formatter.py` | Format inline PR comments | ✅ Existing |
| **SecuritySectionFormatter** | `formatter.py` | Format security findings section | 🆕 Planned |
| **GraphContextFormatter** | `formatter.py` | Format graph analysis section | ✅ Existing |
| **MetricsFormatter** | `formatter.py` | Format metrics (complexity, risk, etc) | ✅ Existing |

### 3.5 Delivery Components

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **GitHubCommenter** | `python/coderabbit_ai/delivery/github_commenter.py` | Post comments to GitHub PR | ✅ Existing |
| **PRSummaryPoster** | `python/coderabbit_ai/delivery/pr_summary_poster.py` | Post summary comment | ✅ Existing |
| **InlineCommentPoster** | `python/coderabbit_ai/delivery/inline_comment_poster.py` | Post inline comments | ✅ Existing |
| **WebhookNotifier** | `python/coderabbit_ai/delivery/webhook_notifier.py` | Send webhook notifications | 🔧 Optional |
| **SlackNotifier** | `python/coderabbit_ai/delivery/slack_notifier.py` | Send Slack notifications | 🔧 Optional |

### 3.6 Metrics & Analytics

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **MetricsCollector** | `python/coderabbit_ai/metrics/collector.py` | Collect review metrics | ✅ Existing |
| **PerformanceTracker** | `python/coderabbit_ai/metrics/performance.py` | Track latency, throughput | ✅ Existing |
| **QualityMetrics** | `python/coderabbit_ai/metrics/quality.py` | Track false positives, user feedback | 🔧 Optional |
| **UsageAnalytics** | `python/coderabbit_ai/metrics/analytics.py` | Track usage patterns | 🔧 Optional |

### 3.7 Data Models (Post-Processing)

| Component | Location | Responsibility | Status |
|-----------|----------|----------------|--------|
| **FinalReview** | `python/coderabbit_ai/models.py` | Complete PR review output | ✅ Existing |
| **PRSummary** | `python/coderabbit_ai/models.py` | Executive summary | ✅ Existing |
| **AggregatedMetrics** | `python/coderabbit_ai/models.py` | Aggregated stats | ✅ Existing |

---

## 🔄 Cross-Phase Components

**These components span multiple phases**

| Component | Location | Responsibility | Phases |
|-----------|----------|----------------|--------|
| **Cache Manager** | `python/coderabbit_ai/cache/manager.py` | Cache graphs, LLM responses | Pre + Processing |
| **Error Handler** | `python/coderabbit_ai/utils/error_handler.py` | Centralized error handling | All phases |
| **Retry Logic** | `python/coderabbit_ai/utils/retry.py` | Retry failed operations | All phases |
| **Rate Limiter** | `python/coderabbit_ai/utils/rate_limiter.py` | Respect API rate limits | Pre + Post |
| **Authentication** | `python/coderabbit_ai/auth/authenticator.py` | GitHub/API authentication | Pre + Post |

---

## 📊 Component Count Summary

| Phase | Total Components | ✅ Existing | 🆕 Planned | 🔧 Optional |
|-------|------------------|-------------|------------|-------------|
| **Phase 1: Pre-Processing** | 28 | 25 | 2 | 1 |
| **Phase 2: Processing** | 35 | 34 | 1 | 0 |
| **Phase 3: Post-Processing** | 29 | 23 | 1 | 5 |
| **Cross-Phase** | 5 | 5 | 0 | 0 |
| **TOTAL** | **97** | **87** | **4** | **6** |

---

## 🎯 New Components for AST-Grep Integration

### Phase 1: Pre-Processing
1. **AstGrepScanner** - Core scanning functionality
2. **SecurityFinding** (model) - Structured security data

### Phase 2: Processing
3. **Security Risk Weight Calculator** - Enhance ReviewAgent

### Phase 3: Post-Processing
4. **SecurityAggregator** - Aggregate and prioritize security findings

---

## 🚀 Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      PHASE 1: PRE-PROCESSING                     │
├─────────────────────────────────────────────────────────────────┤
│  1. PRInputCollector → Fetch PR data from GitHub                │
│  2. CodeChangeParser → Parse diffs                              │
│  3. RepoStructureAnalyzer → Analyze repo layout                 │
│  4. StaticAnalysisAggregator → Run linters + ast-grep          │
│  5. DependencyGraphBuilder → Build dependency graph             │
│  6. DeepWikiClient → Query architectural docs                   │
│  7. HybridContextProvider → Combine graph + DeepWiki            │
│  8. ContextAdapter → Convert to Pydantic models                 │
│  9. ContextData → Store all collected data                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      PHASE 2: PROCESSING                         │
├─────────────────────────────────────────────────────────────────┤
│  1. ContextEngineeringAgent → Enrich with all context          │
│     • Format static analysis                                    │
│     • Format security findings                                  │
│     • Format graph context                                      │
│     • Format DeepWiki docs                                      │
│  2. ReviewAgent → Analyze code changes                          │
│     • Calculate complexity (size, structure, logic, context)    │
│     • Add graph complexity (20% weight)                         │
│     • Add security risk (15% weight)                            │
│     • Generate review comments                                  │
│  3. VerificationAgent(s) → Specialized validation               │
│     • Security specialist validates ast-grep findings           │
│     • Performance specialist checks bottlenecks                 │
│     • Style specialist checks conventions                       │
│  4. AgentOrchestrator → Coordinate execution                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 3: POST-PROCESSING                      │
├─────────────────────────────────────────────────────────────────┤
│  1. ResponseAggregator → Combine all agent outputs              │
│  2. SecurityAggregator → Dedupe, prioritize security findings   │
│  3. CommentDeduplicator → Remove duplicate comments             │
│  4. PriorityScorer → Rank by severity × impact × confidence     │
│  5. OutputFormatter → Generate markdown                         │
│     • Summary section                                           │
│     • Security findings section                                 │
│     • Graph impact section                                      │
│     • Inline comments                                           │
│  6. GitHubCommenter → Post to PR                                │
│  7. MetricsCollector → Track performance                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 Notes

- **Modularity**: Each component is independently testable
- **Extensibility**: New analyzers/agents can be added without modifying core flow
- **Parallelization**: Components within same phase can run concurrently
- **Error Isolation**: Failure in one component doesn't cascade to others
- **Caching**: Expensive operations (graph building, LLM calls) are cached

---

## 🔗 Integration Points

### Phase 1 → Phase 2
- **ContextData** is the contract between phases
- All pre-processing results stored in ContextData
- Processing agents consume ContextData

### Phase 2 → Phase 3
- **Agent Responses** are the contract between phases
- All agent outputs collected by ResponseAggregator
- Post-processing operates on aggregated responses

### Phase 3 → External Systems
- **GitHub API** for posting comments
- **Metrics backend** for analytics
- **Webhooks/Slack** for notifications
