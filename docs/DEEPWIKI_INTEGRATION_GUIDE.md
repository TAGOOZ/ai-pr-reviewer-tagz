# DeepWiki Integration Guide

## Overview

DeepWiki is an AI-powered documentation platform by Cognition AI that provides semantic understanding of 50,000+ public GitHub repositories. This integration adds Layer 2 (semantic context) to CodeRabbit's three-layer context system.

### Three-Layer Context Architecture

```
CodeRabbit Context System
├── Layer 1: Dependency Graph (ALWAYS) - Structure-based analysis
├── Layer 2: DeepWiki (IF AVAILABLE) - Semantic documentation    ← This Integration
└── Layer 3: On-Demand LLM (FALLBACK) - Generated docs
```

**Benefits**:
- **100% Coverage**: Works for all repos (graceful degradation)
- **Optimal Quality**: Use best available context source
- **Zero Cost**: DeepWiki is free for public repos

---

## Quick Start

### 1. Basic Usage

```python
from coderabbit_ai.integrations.deepwiki_client import DeepWikiClient

# Initialize client
client = DeepWikiClient()

# Check if repo is indexed
if client.is_repo_indexed("facebook/react"):
    # Ask questions about the repository
    answer = client.ask_question(
        "facebook/react",
        "What is the reconciliation algorithm?"
    )
    print(answer)

    # Get wiki structure
    structure = client.read_wiki_structure("facebook/react")
    print(f"Documentation sections: {structure['sections']}")
```

### 2. PR Review Integration (Recommended)

```python
from coderabbit_ai.integrations.hybrid_context_provider import (
    HybridContextProvider
)

# Initialize provider
provider = HybridContextProvider(
    project_root="/path/to/repo",
    repo_name="facebook/react",
    enable_deepwiki=True  # Enable Layer 2
)

# Enrich PR context
context = provider.enrich_pr_context(
    changed_files=["src/React.js", "src/ReactHooks.js"],
    pr_description="Add new useEffect hook"
)

# Check which context sources are available
print(f"Context sources: {context.get_context_sources()}")
# Output: ['graph', 'deepwiki']

# Format for LLM
llm_prompt = provider.format_for_llm(context)

# Get risk summary
risk = provider.get_risk_summary(context)
print(f"Risk: {risk['risk_level']}")
print(f"Impact: {risk['impact_score']:.1%}")
```

---

## Configuration

### Environment Variables

Add to `.env` or environment:

```bash
# DeepWiki Configuration (Layer 2)
DEEPWIKI_ENABLED=true
DEEPWIKI_MCP_URL=https://mcp.deepwiki.com/mcp
DEEPWIKI_SSE_URL=https://mcp.deepwiki.com/sse
DEEPWIKI_TIMEOUT=30
DEEPWIKI_CACHE_TTL=3600
DEEPWIKI_MAX_RETRIES=3

# Devin Configuration (optional, for private repos)
DEVIN_API_KEY=                    # Leave empty if not using
DEVIN_API_URL=https://api.devin.ai
DEVIN_TIMEOUT=30
DEVIN_AUTO_REQUEST_INDEXING=false
```

### Python Configuration

```python
from coderabbit_ai import config

# Check current settings
print(config.DEEPWIKI_ENABLED)      # True
print(config.DEEPWIKI_MCP_URL)      # https://mcp.deepwiki.com/mcp
print(config.DEEPWIKI_CACHE_TTL)    # 3600

# Override programmatically (before creating clients)
config.DEEPWIKI_TIMEOUT = 60
config.DEEPWIKI_CACHE_TTL = 7200
```

---

## API Reference

### DeepWikiClient

Main client for interacting with DeepWiki MCP server.

#### `__init__(mcp_url, sse_url, timeout, cache_ttl, max_retries)`

Initialize DeepWiki client.

```python
client = DeepWikiClient(
    mcp_url="https://mcp.deepwiki.com/mcp",
    sse_url="https://mcp.deepwiki.com/sse",
    timeout=30,
    cache_ttl=3600,
    max_retries=3
)
```

#### `is_repo_indexed(repo: str) -> bool`

Check if repository is indexed in DeepWiki's 50k database.

```python
if client.is_repo_indexed("facebook/react"):
    print("Repository is indexed")
else:
    print("Repository not in DeepWiki index")
```

#### `ask_question(repo: str, question: str) -> Optional[str]`

Ask natural language question about repository.

```python
answer = client.ask_question(
    "facebook/react",
    "How does the fiber reconciler work?"
)
print(answer)
```

**Common Questions**:
- "What is the architecture of [component]?"
- "How does [feature] work?"
- "What are the dependencies of [file]?"
- "What coding patterns are used in [module]?"

#### `read_wiki_structure(repo: str) -> Optional[Dict]`

Get documentation structure.

```python
structure = client.read_wiki_structure("facebook/react")
print(structure['sections'])  # ['Overview', 'Architecture', 'API']
print(structure['pages'])      # ['intro', 'hooks', 'components']
```

#### `read_wiki_contents(repo: str, page: str) -> Optional[str]`

Read specific wiki page content.

```python
content = client.read_wiki_contents(
    "facebook/react",
    "architecture/reconciliation"
)
print(content)  # Markdown content
```

#### `get_component_relationships(repo: str, file_path: str) -> Optional[Dict]`

Get semantic relationships for a file.

```python
rels = client.get_component_relationships(
    "facebook/react",
    "packages/react-reconciler/src/ReactFiber.js"
)
print(rels['raw_answer'])
```

#### `enrich_pr_context(repo: str, changed_files: List[str]) -> DeepWikiContext`

Get comprehensive context for PR review.

```python
context = client.enrich_pr_context(
    "facebook/react",
    ["src/React.js"],
    "Add new hook API"
)

print(context.architectural_overview)
print(context.patterns_and_conventions)
```

#### `format_for_llm(context: DeepWikiContext) -> str`

Format context for LLM consumption.

```python
formatted = client.format_for_llm(context)
# Returns formatted markdown string
```

---

### HybridContextProvider

Unified provider combining all three context layers.

#### `__init__(project_root, repo_name, enable_deepwiki, cache_ttl)`

Initialize hybrid provider.

```python
provider = HybridContextProvider(
    project_root="/path/to/repo",
    repo_name="facebook/react",
    enable_deepwiki=True,
    cache_ttl=3600
)
```

#### `enrich_pr_context(changed_files, pr_description) -> HybridContext`

Main method for getting comprehensive PR context.

```python
context = provider.enrich_pr_context(
    changed_files=["src/module.py"],
    pr_description="Fix bug in authentication"
)

# Check available context
print(context.get_context_sources())  # ['graph', 'deepwiki']

# Access layer-specific context
print(context.graph_context['impact_analysis']['risk_level'])
print(context.deepwiki_context.architectural_overview)
```

#### `format_for_llm(context: HybridContext) -> str`

Format all context layers for LLM.

```python
llm_input = provider.format_for_llm(context)
# Returns unified markdown with all layers
```

#### `get_risk_summary(context: HybridContext) -> Dict`

Extract risk summary from context.

```python
risk = provider.get_risk_summary(context)
print(f"Risk: {risk['risk_level']}")
print(f"Impact: {risk['impact_score']:.1%}")
print(f"Sources: {risk['context_sources']}")
```

#### `should_flag_for_review(context, threshold) -> bool`

Determine if PR needs extra review.

```python
if provider.should_flag_for_review(context, threshold='high'):
    print("⚠️  This PR needs senior reviewer")
```

---

## Private Repository Support

DeepWiki's 50k index covers public repos only. For private repositories, use Devin integration.

### Setup Devin Integration

1. **Get Devin API Key**: Sign up at https://devin.ai
2. **Set Environment Variable**:
   ```bash
   export DEVIN_API_KEY="your-api-key-here"
   ```

3. **Request Indexing**:
   ```python
   from coderabbit_ai.integrations.devin_client import DevinClient

   devin = DevinClient(api_key="your-key")

   # Request indexing
   result = devin.request_indexing("myorg/private-repo")
   print(f"Request ID: {result['request_id']}")
   print(f"Estimated time: {result['estimated_time']}")
   ```

4. **Check Status**:
   ```python
   from coderabbit_ai.integrations.devin_client import IndexingStatus

   status = devin.check_indexing_status("myorg/private-repo")

   if status == IndexingStatus.COMPLETED:
       print("✅ Repository indexed! You can now use DeepWiki.")
   elif status == IndexingStatus.IN_PROGRESS:
       print("⏳ Indexing in progress...")
   ```

5. **Auto-Request (Optional)**:
   ```python
   # Automatically request indexing if needed
   result = devin.auto_request_if_needed(
       "myorg/private-repo",
       auto_request=True  # Auto-submit request
   )
   print(result['message'])
   ```

---

## Integration Patterns

### Pattern 1: Automatic Fallback

Let the system automatically choose the best context source:

```python
provider = HybridContextProvider(
    project_root="/path/to/repo",
    repo_name="owner/repo",
    enable_deepwiki=True  # Tries DeepWiki, falls back to graph
)

context = provider.enrich_pr_context(changed_files)

# System automatically:
# 1. Checks if repo indexed
# 2. Uses DeepWiki if available
# 3. Falls back to graph-only if not
```

### Pattern 2: Explicit Layer Control

Control which layers to use:

```python
# Graph only (fastest, always works)
provider_graph = HybridContextProvider(
    project_root="/path/to/repo",
    enable_deepwiki=False
)

# Graph + DeepWiki (best quality for public repos)
provider_hybrid = HybridContextProvider(
    project_root="/path/to/repo",
    repo_name="owner/repo",
    enable_deepwiki=True
)
```

### Pattern 3: Direct DeepWiki Queries

Use DeepWiki client directly for specific questions:

```python
client = DeepWikiClient()

# Ask architectural questions during review
if "auth" in changed_file_path:
    auth_context = client.ask_question(
        repo,
        "What is the authentication flow and which modules are involved?"
    )
    # Use in review comments
```

### Pattern 4: Caching Strategy

Optimize performance with caching:

```python
provider = HybridContextProvider(
    project_root="/path/to/repo",
    repo_name="owner/repo",
    cache_ttl=7200  # 2 hours
)

# First PR - builds cache
context1 = provider.enrich_pr_context(changed_files1)

# Subsequent PRs - uses cache
context2 = provider.enrich_pr_context(changed_files2)  # Fast!

# Clear caches if needed
provider.clear_all_caches()
```

---

## Performance Considerations

### Latency

- **Graph Analysis**: 1-3s (local)
- **DeepWiki Query**: 200-500ms per query
- **Total (Hybrid)**: 2-5s for typical PR

### Optimization Tips

1. **Enable Caching**:
   ```python
   DEEPWIKI_CACHE_TTL=7200  # 2 hours
   ```

2. **Limit File Count**:
   ```python
   # Hybrid provider limits to first 3 files for DeepWiki
   context = provider.enrich_pr_context(
       changed_files[:10]  # Only analyze first 10
   )
   ```

3. **Use Async (Future)**:
   ```python
   # Not yet implemented, but planned
   context = await provider.enrich_pr_context_async(changed_files)
   ```

### Cost

- **DeepWiki**: **FREE** (no authentication required)
- **Devin**: Pay-per-index for private repos (check Devin pricing)
- **Local Graph**: FREE (computational cost only)

---

## Troubleshooting

### Repository Not Found

**Problem**: `is_repo_indexed()` returns `False`

**Solutions**:
1. **Public Repo**: Not in DeepWiki's 50k index. System falls back to graph-only.
2. **Private Repo**: Use Devin integration to request indexing.
3. **New Repo**: Popular repos added regularly, check again later.

### Timeout Errors

**Problem**: Requests timing out

**Solutions**:
```python
# Increase timeout
client = DeepWikiClient(timeout=60)

# Or via environment
export DEEPWIKI_TIMEOUT=60
```

### Rate Limiting

**Problem**: Too many requests

**Solutions**:
1. **Increase Cache TTL**:
   ```python
   DEEPWIKI_CACHE_TTL=7200  # Cache for 2 hours
   ```

2. **Reduce Query Frequency**:
   ```python
   # Only query on important PRs
   if len(changed_files) > 5 or risk_level == 'HIGH':
       use_deepwiki = True
   ```

### Cache Not Working

**Problem**: Repeated queries hitting API

**Solution**:
```python
# Check cache stats
stats = client.get_cache_stats()
print(f"Cached: {stats['fresh_items']}/{stats['total_items']}")

# Clear stale cache
client.clear_cache()
```

---

## Examples

### Example 1: Simple Review with DeepWiki

```python
from coderabbit_ai.integrations.hybrid_context_provider import HybridContextProvider

# Setup
provider = HybridContextProvider(
    project_root="/workspace/myproject",
    repo_name="facebook/react",
    enable_deepwiki=True
)

# Review PR
context = provider.enrich_pr_context(
    changed_files=["src/ReactHooks.js"],
    pr_description="Add useEffect dependency tracking"
)

# Generate review comment
if context.deepwiki_available:
    comment = f"""
    ## Code Review

    **Risk Level**: {context.graph_context['impact_analysis']['risk_level']}

    **Architectural Context** (via DeepWiki):
    {context.deepwiki_context.architectural_overview}

    **Recommendations**:
    {' '.join(f'- {r}' for r in context.graph_context['recommendations'])}
    """
    print(comment)
```

### Example 2: Private Repo with Devin

```python
from coderabbit_ai.integrations.devin_client import DevinClient
from coderabbit_ai.integrations.hybrid_context_provider import HybridContextProvider
import time

# Setup Devin
devin = DevinClient(api_key=os.getenv("DEVIN_API_KEY"))

# Request indexing if needed
result = devin.auto_request_if_needed(
    "myorg/private-repo",
    auto_request=True
)

if result['needs_wait']:
    print(f"⏳ {result['message']}")
    print("Using graph-only context for now...")

# Use graph-only while indexing
provider = HybridContextProvider(
    project_root="/workspace/private-repo",
    repo_name="myorg/private-repo",
    enable_deepwiki=False  # Disable until indexed
)

context = provider.enrich_pr_context(changed_files)
```

### Example 3: Conditional DeepWiki Usage

```python
from coderabbit_ai.integrations.hybrid_context_provider import HybridContextProvider

provider = HybridContextProvider(
    project_root="/workspace/repo",
    repo_name="owner/repo",
    enable_deepwiki=True
)

def review_pr(changed_files, pr_size):
    """Review PR with appropriate context level."""

    context = provider.enrich_pr_context(changed_files)
    risk = provider.get_risk_summary(context)

    # Use semantic context for complex PRs
    if pr_size == "large" or risk['risk_level'] in ['HIGH', 'CRITICAL']:
        if context.deepwiki_available:
            print("📚 Using enhanced semantic context")
            return provider.format_for_llm(context)
        else:
            print("⚠️  Large PR but no semantic context available")

    # Graph-only for small PRs
    return provider.graph_provider.format_for_llm(context.graph_context)
```

---

## Best Practices

### 1. Always Enable DeepWiki

**✅ DO**:
```python
provider = HybridContextProvider(
    enable_deepwiki=True  # Gracefully falls back if unavailable
)
```

**❌ DON'T**:
```python
# Don't disable unless you have a good reason
provider = HybridContextProvider(
    enable_deepwiki=False
)
```

### 2. Check Context Sources

**✅ DO**:
```python
context = provider.enrich_pr_context(changed_files)

if 'deepwiki' in context.get_context_sources():
    # Leverage semantic context
    use_architectural_analysis()
else:
    # Fall back to structure-only analysis
    use_basic_analysis()
```

### 3. Cache Aggressively

**✅ DO**:
```python
# Long TTL for stable repos
provider = HybridContextProvider(
    cache_ttl=7200  # 2 hours
)
```

### 4. Handle Failures Gracefully

**✅ DO**:
```python
try:
    context = provider.enrich_pr_context(changed_files)
    if context.deepwiki_context:
        # Use semantic context
        pass
    else:
        # Fall back to graph context (always available)
        pass
except Exception as e:
    logger.warning(f"Context enrichment failed: {e}")
    # Continue with basic analysis
```

---

## FAQ

**Q: Does DeepWiki work for private repositories?**
A: Not directly. Use Devin integration to request indexing for private repos.

**Q: How often is DeepWiki's index updated?**
A: Popular repos are updated regularly. Repos with DeepWiki badge update automatically.

**Q: What if my repo isn't indexed?**
A: System automatically falls back to graph-based analysis. No manual intervention needed.

**Q: Can I use DeepWiki without the graph layer?**
A: Not recommended. Graph layer (Layer 1) is the foundation and always fast. DeepWiki enhances it.

**Q: Is there a rate limit?**
A: Not officially published. Internal caching prevents hitting limits in normal use.

**Q: How do I know if DeepWiki is working?**
A: Check logs or `context.get_context_sources()`. Should include 'deepwiki' if available.

---

## Next Steps

1. ✅ **You're ready!** Start using `HybridContextProvider` in your review pipeline
2. 📖 Read: [Graph Quick Start](GRAPH_QUICK_START.md) for Layer 1 details
3. 🧪 Experiment: Try different repos to see quality differences
4. ⚙️ Optimize: Tune cache TTL and timeouts for your use case
5. 📊 Monitor: Track which context sources are used in production

---

## Support

- **Documentation**: This guide + [GRAPH_QUICK_START.md](GRAPH_QUICK_START.md)
- **Tests**: `tests/integrations/test_deepwiki_integration.py`
- **Code**: `python/coderabbit_ai/integrations/`
- **Issues**: Report bugs or suggestions to the team
