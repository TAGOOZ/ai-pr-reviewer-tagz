# Graph-Based Dependency Analysis - Quick Start Guide

## 5-Minute Setup

### 1. Basic Usage

```python
from coderabbit_ai.graph import DependencyGraph, ImpactAnalyzer

# Build graph for your repository
graph = DependencyGraph("/path/to/repo")
graph.build_graph()  # Takes 1-3 seconds for most repos

# Analyze impact of changes
analyzer = ImpactAnalyzer(graph)
analysis = analyzer.analyze_changes(["src/auth.py", "src/api.py"])

# Get results
print(f"Risk: {analysis.risk_level}")  # LOW, MEDIUM, HIGH, CRITICAL
print(f"Impact: {analysis.impact_score:.1%}")  # Percentage of codebase
print(f"Affected: {len(analysis.transitively_affected)} files")
```

### 2. CAG Integration

```python
from coderabbit_ai.graph.cag_integration import GraphContextProvider

# Create provider (singleton, caches graph)
provider = GraphContextProvider("/repo/path")

# Enrich PR context
context = provider.enrich_pr_context(changed_files)

# Use in review
llm_context = provider.format_for_llm(context)
```

### 3. Common Queries

```python
# What does this file depend on?
dependencies = graph.get_dependencies("src/module.py")

# What depends on this file?
dependents = graph.get_dependents("src/module.py")

# Get metrics for a file
metrics = graph.get_metrics("src/module.py")
print(f"Fan-in: {metrics.fan_in}")  # How many files import this
print(f"Fan-out: {metrics.fan_out}")  # How many files this imports
print(f"Is hub: {metrics.is_hub}")  # True if heavily used

# Find circular dependencies
cycles = graph.find_cycles()
```

## Integration with Review Pipeline

```python
# In your review agent
def review_pr(pr_data):
    # ... existing code ...

    # Add graph context
    graph_provider = GraphContextProvider(repo_path)
    graph_context = graph_provider.enrich_pr_context(pr_data.changed_files)

    # Check risk level
    if graph_context['impact_analysis']['risk_level'] in ['HIGH', 'CRITICAL']:
        # Flag for extra review
        pr_data.add_label("high-impact")
        pr_data.request_senior_reviewer()

    # Add to LLM context
    context_for_llm = f"""
    {graph_provider.format_for_llm(graph_context)}

    Code changes:
    {pr_data.diff}
    """

    # Continue with review...
```

## Supported Languages

| Language | Status | Features |
|----------|--------|----------|
| Python | ✅ Full | AST parsing, relative imports |
| JavaScript | ✅ Full | ES6, CommonJS, dynamic imports |
| TypeScript | ✅ Full | Same as JavaScript |
| Go | ✅ Full | Import blocks, standard lib detection |
| Java | 🔄 Planned | Easy to add |
| Rust | 🔄 Planned | Easy to add |

## Performance

- **Build**: 1-3s for 500 files, 10-15s for 2000 files
- **Queries**: <1ms per query
- **Memory**: ~100MB for 500 files
- **Cache**: 1 hour TTL (configurable)

## When to Use

✅ **Use graph analysis for:**
- Impact assessment of PRs
- Risk-based review prioritization
- Dependency understanding
- Architectural insights
- Finding circular dependencies
- Related changes finder

❌ **Don't use for:**
- Single-file changes (overkill)
- Repos with <10 files (not worth it)
- Non-code repositories

## Next Steps

1. **Test on your repo**: Build graph and explore
2. **Integrate with CAG**: Add to review pipeline
3. **Configure thresholds**: Adjust risk levels in config
4. **Monitor metrics**: Track impact accuracy

## Support

- **Documentation**: `docs/GRAPH_DEPENDENCY_ANALYSIS_COMPLETE.md`
- **Tests**: `tests/graph/test_dependency_graph.py`
- **Code**: `python/coderabbit_ai/graph/`
