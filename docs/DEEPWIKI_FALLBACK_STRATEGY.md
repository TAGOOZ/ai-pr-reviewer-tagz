# DeepWiki Fallback Strategy for Non-Indexed Repositories

## Problem Statement

DeepWiki has 50,000+ **public** repositories pre-indexed. However:

1. **Private repos** require Devin account integration
2. **New/smaller public repos** may not be indexed
3. **Custom/internal repos** won't be in DeepWiki's database

**Question**: How do we handle repos that aren't in DeepWiki's 50k index?

---

## Solution: Multi-Layer Fallback Strategy

### Architecture Overview

```
CodeRabbit Context System (Layered)
├── Layer 1: Local Dependency Graph (ALWAYS AVAILABLE) ← We just built this!
├── Layer 2: DeepWiki Semantic Context (if repo indexed)
└── Layer 3: On-Demand Documentation Generation (fallback)
```

---

## Layer 1: Local Dependency Graph (Foundation)

**What We Built**: Graph-based dependency analysis

**Capabilities**:
- Import/export analysis
- Impact calculation
- Component relationships
- Circular dependency detection

**Advantages**:
- ✅ Works for ALL repos (public/private)
- ✅ No external dependencies
- ✅ Fast (local computation)
- ✅ Always up-to-date

**Limitations**:
- ❌ No semantic understanding
- ❌ No architectural documentation
- ❌ Structure-only, no intent

---

## Layer 2: DeepWiki (When Available)

**Check Availability**:
```python
def is_repo_indexed(repo: str) -> bool:
    """Check if repo is in DeepWiki's index."""
    try:
        response = requests.get(
            f"https://deepwiki.com/{repo}",
            timeout=5
        )
        return response.status_code == 200
    except:
        return False
```

**Usage**:
```python
if is_repo_indexed(pr_data.repo):
    # Use DeepWiki for rich semantic context
    semantic_context = deepwiki.enrich_pr_context(...)
else:
    # Fall back to Layer 3
    semantic_context = generate_on_demand_context(...)
```

---

## Layer 3: On-Demand Documentation (Fallback)

### Option A: LLM-Based Documentation Generation (Recommended)

**Approach**: Use Claude/GPT-4 to generate documentation on-the-fly

```python
class OnDemandDocGenerator:
    """Generate documentation for non-indexed repos."""

    def generate_component_docs(
        self,
        changed_files: List[str],
        context: Dict
    ) -> str:
        """Generate documentation for changed components."""

        # Use dependency graph to understand relationships
        dependencies = dependency_graph.get_dependencies(file)
        dependents = dependency_graph.get_dependents(file)

        # Build prompt for LLM
        prompt = f"""
        Analyze this code component and generate documentation:

        File: {file}
        Dependencies: {dependencies}
        Dependents: {dependents}

        Code:
        {read_file(file)[:5000]}  # First 5k chars

        Generate:
        1. Component purpose
        2. Key responsibilities
        3. Architectural role
        4. Integration points
        """

        # Call LLM (Claude Sonnet)
        docs = claude_client.generate(prompt)
        return docs
```

**Advantages**:
- ✅ Works for any repo
- ✅ Customized to specific changes
- ✅ Uses existing LLM infrastructure
- ✅ Can cache results

**Considerations**:
- Token cost (mitigated by caching)
- Latency (run in parallel)
- Quality (use good prompts)

### Option B: Static Analysis Documentation

**Approach**: Generate docs from code structure

```python
def generate_static_docs(file_path: str) -> Dict:
    """Generate documentation from code analysis."""
    return {
        'classes': extract_classes(file_path),
        'functions': extract_functions(file_path),
        'dependencies': graph.get_dependencies(file_path),
        'complexity': calculate_complexity(file_path),
        'purpose': infer_purpose_from_name(file_path)
    }
```

**Advantages**:
- ✅ Fast
- ✅ No external calls
- ✅ Deterministic

**Limitations**:
- ❌ No semantic understanding
- ❌ Limited architectural insight

### Option C: Hybrid Approach (BEST)

**Combine local analysis + targeted LLM calls**:

```python
def get_semantic_context(repo: str, changed_files: List[str]):
    """Get semantic context with fallback."""

    # Try DeepWiki first
    if is_repo_indexed(repo):
        return deepwiki.enrich_pr_context(repo, changed_files)

    # Fallback: Use local graph + targeted LLM
    context = {}

    # 1. Get structural info (fast, local)
    for file in changed_files:
        context[file] = {
            'dependencies': graph.get_dependencies(file),
            'dependents': graph.get_dependents(file),
            'metrics': graph.get_metrics(file),
            'component': extract_component_name(file)
        }

    # 2. Generate semantic docs for key files only
    critical_files = [
        f for f in changed_files
        if context[f]['metrics'].is_hub  # High impact files
    ]

    for file in critical_files:
        context[file]['semantic_docs'] = generate_component_docs(
            file,
            context[file]
        )

    return context
```

---

## Devin Account Integration (For Private Repos)

### When Needed
- Private repositories
- Repos not in 50k public index
- Custom enterprise repos

### Integration Approach

```python
class DevinIntegration:
    """Integration with Devin for private repo indexing."""

    def __init__(self, devin_api_key: Optional[str] = None):
        self.api_key = devin_api_key
        self.enabled = api_key is not None

    def request_indexing(self, repo: str) -> bool:
        """Request Devin to index a private repository."""
        if not self.enabled:
            return False

        # Call Devin API to queue indexing
        response = requests.post(
            "https://api.devin.ai/deepwiki/index",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"repository": repo}
        )

        return response.status_code == 202  # Accepted

    def check_indexing_status(self, repo: str) -> str:
        """Check if repo indexing is complete."""
        # Returns: 'not_started', 'in_progress', 'completed', 'failed'
        pass
```

### User Experience

```python
# Configuration
DEVIN_API_KEY = os.getenv("DEVIN_API_KEY")  # Optional

# Usage
if not deepwiki.is_repo_indexed(repo):
    if DEVIN_API_KEY:
        # Try to request indexing
        if devin.request_indexing(repo):
            logger.info(f"Requested indexing for {repo} via Devin")
            # Fall back to on-demand for now
            context = generate_on_demand_context(...)
    else:
        # No Devin key, use on-demand generation
        context = generate_on_demand_context(...)
```

---

## Decision Matrix

| Repo Type | Available Method | Fallback Method | Cost |
|-----------|-----------------|-----------------|------|
| **Public (in 50k)** | DeepWiki API | Local graph | Free |
| **Public (not in 50k)** | Local graph + LLM | Static analysis | Low (cached) |
| **Private (with Devin)** | Request indexing | Local graph + LLM | Devin pricing |
| **Private (no Devin)** | Local graph + LLM | Static analysis | Low (cached) |

---

## Implementation Phases

### Phase 1: Local Graph (DONE ✅)
- Built dependency graph
- Import parsers
- Impact analysis

### Phase 2: DeepWiki Integration (2 weeks)
- Implement MCP client
- Add availability checking
- Integrate with CAG

### Phase 3: On-Demand Generation (1 week)
- LLM-based doc generation
- Caching layer
- Hybrid context builder

### Phase 4: Devin Integration (OPTIONAL, 1 week)
- API client for private repos
- Indexing request queue
- Status monitoring

---

## Recommended Configuration

```python
# config.py

# DeepWiki (free, public repos)
DEEPWIKI_ENABLED = get_env_bool("DEEPWIKI_ENABLED", True)
DEEPWIKI_MCP_URL = "https://mcp.deepwiki.com/mcp"

# On-demand generation (fallback)
ON_DEMAND_DOCS_ENABLED = get_env_bool("ON_DEMAND_DOCS_ENABLED", True)
ON_DEMAND_CACHE_TTL = get_env_int("ON_DEMAND_CACHE_TTL", 86400)  # 24h

# Devin integration (optional, for private repos)
DEVIN_API_KEY = get_env_str("DEVIN_API_KEY", None)
DEVIN_AUTO_REQUEST_INDEXING = get_env_bool("DEVIN_AUTO_REQUEST", False)
```

---

## Cost Analysis

### DeepWiki (Layer 2)
- **Cost**: Free
- **Coverage**: 50k+ public repos
- **Latency**: ~100-500ms

### On-Demand LLM (Layer 3)
- **Cost**: ~$0.01-0.05 per PR (with caching)
- **Coverage**: All repos
- **Latency**: ~1-3s per component
- **Optimization**: Cache aggressively, only analyze critical files

### Devin Integration (Optional)
- **Cost**: Devin pricing (TBD)
- **Coverage**: Private repos
- **Latency**: Indexing takes hours, queries fast

---

## Conclusion

**Strategy**: Use **layered fallback** approach

1. **Always use** local dependency graph (Layer 1)
2. **Try** DeepWiki if repo indexed (Layer 2)
3. **Fall back** to on-demand LLM generation (Layer 3)
4. **Optionally** integrate Devin for private repos

**Benefits**:
- ✅ Works for 100% of repos
- ✅ Optimal performance for indexed repos
- ✅ Reasonable fallback for others
- ✅ Flexible Devin integration

**Next Steps**:
1. ✅ Implement Layer 1 (dependency graph) - DONE
2. [ ] Implement Layer 2 (DeepWiki) - 2 weeks
3. [ ] Implement Layer 3 (on-demand) - 1 week
4. [ ] Add Devin integration (optional) - 1 week if needed
