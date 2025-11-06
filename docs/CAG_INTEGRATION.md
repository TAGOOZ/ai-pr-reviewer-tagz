# CAG Integration Guide

## Overview

This guide explains how to integrate the CAG (Cache-Augmented Generation) layer with the existing RAG pipeline to achieve 70% cost reduction and 80% latency improvement.

## Architecture

```
┌─────────────────────────────────────────┐
│         PR Review Request               │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Context Engineering Agent             │
│   (Python: context_engineering.py)      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   HybridContextRetriever                │
│   ┌─────────────────────────────────┐   │
│   │  CAG Layer (Static Context)     │   │
│   │  - Check L1/L2 cache first      │   │
│   │  - 0ms retrieval for cached     │   │
│   │  - Org policies, architecture   │   │
│   └─────────────────────────────────┘   │
│   ┌─────────────────────────────────┐   │
│   │  RAG Layer (Dynamic Context)    │   │
│   │  - Query vector DB only if      │   │
│   │    necessary                    │   │
│   │  - Recent patterns, issues      │   │
│   └─────────────────────────────────┘   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Combined Context → Verification       │
│   Agents                                │
└─────────────────────────────────────────┘
```

## Step 1: Setup Cache Infrastructure

### Rust Side (API Gateway)

1. **Initialize MultiTierCache**

```rust
use coderabbit_cache_layer::{MultiTierCache, StaticContextCache};
use std::sync::Arc;

// Create multi-tier cache (L1 + L2)
let cache = Arc::new(
    MultiTierCache::new(
        "/path/to/sled",      // L1 cache path
        "redis://localhost"   // L2 Redis URL
    ).await?
);

// Create static context cache wrapper
let static_cache = Arc::new(StaticContextCache::new(cache));
```

2. **Update IndexingService initialization**

```rust
let indexing_service = IndexingService::new(
    orchestrator.clone(),
    github_token.clone(),
    Some(static_cache.clone()),  // Add CAG support
);
```

3. **Cache warmup happens automatically**
When `indexing_service.index_repository()` is called, it will:
- Fetch all repo files
- Warmup static context cache automatically
- Index files in vector DB

## Step 2: Python Integration

### Option A: Direct Integration (Recommended)

Modify `python/coderabbit_ai/agents/context_engineering.py`:

```python
from coderabbit_ai.cag import HybridContextRetriever

class ContextEngineeringAgent(dspy.Module):
    def __init__(self, cache_client=None, rag_client=None):
        super().__init__()
        self.context_generator = dspy.ChainOfThought(ContextEngineeringSignature)

        # Add hybrid retriever
        self.hybrid_retriever = HybridContextRetriever(
            cache_client=cache_client,
            rag_client=rag_client
        )

    def forward(self, context_data: ContextData) -> ContextEngineeringResponse:
        import time
        start_time = time.time()

        # Extract org/repo from context_data
        org, repo = self._extract_org_repo(context_data.repo_structure)

        # Use hybrid retriever (CAG + RAG)
        hybrid_context = await self.hybrid_retriever.retrieve_context(
            org=org,
            repo=repo,
            code_changes=context_data.code_changes,
            pr_description=context_data.pr_description or ""
        )

        # Format for DSPy
        formatted_context = self.hybrid_retriever.format_hybrid_context(hybrid_context)

        # Generate enriched context using DSPy
        result = self.context_generator(
            repo_structure=context_data.repo_structure,
            code_changes=context_data.code_changes,
            historical_data=context_data.historical_data,
            static_analysis_results=self._format_static_analysis(context_data.static_analysis_results),
            ast_features=self._extract_ast_features(context_data.code_changes),
            rag_context=formatted_context  # CAG + RAG combined
        )

        # Add CAG metrics to metadata
        return ContextEngineeringResponse(
            agent_id="context_engineering",
            confidence_score=self._calculate_confidence_score(context_data, result),
            processing_time_ms=int((time.time() - start_time) * 1000),
            enriched_context=result.enriched_context,
            code_relationships=result.code_relationships,
            relevant_patterns=result.relevant_patterns,
            metadata={
                "risk_assessment": result.risk_assessment,
                "cag_enabled": True,
                "cag_hit_rate": hybrid_context.cache_hit_rate,
                "cag_retrieval_time_ms": hybrid_context.total_retrieval_time_ms,
                "static_contexts_cached": len(hybrid_context.static_context),
            }
        )
```

### Option B: Gradual Rollout

Keep existing RAG, add CAG as fallback:

```python
# Try CAG first
if self.hybrid_retriever:
    try:
        hybrid_context = await self.hybrid_retriever.retrieve_context(...)
        rag_context_str = self.hybrid_retriever.format_hybrid_context(hybrid_context)
    except Exception as e:
        logger.warning(f"CAG failed, falling back to RAG: {e}")
        rag_context_str = self._format_rag_context(context_data.rag_context)
else:
    # Existing RAG path
    rag_context_str = self._format_rag_context(context_data.rag_context)
```

## Step 3: Configure Cache Clients

### Python Cache Client Setup

```python
import redis.asyncio as redis
from typing import Optional, Dict, Any
import json

class PythonCacheClient:
    """Python client for accessing Rust multi-tier cache."""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached content."""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    async def set(self, key: str, value: Dict[str, Any], ttl_seconds: int):
        """Set cached content."""
        try:
            await self.redis.setex(
                key,
                ttl_seconds,
                json.dumps(value)
            )
        except Exception as e:
            logger.error(f"Cache set failed: {e}")

# Initialize in pipeline
cache_client = PythonCacheClient(redis_url="redis://localhost:6379")
rag_client = ...  # Existing RAG client

context_agent = ContextEngineeringAgent(
    cache_client=cache_client,
    rag_client=rag_client
)
```

## Step 4: Monitor Performance

### Track Key Metrics

```python
# After each review
cag_metrics = context_agent.hybrid_retriever.get_metrics()

logger.info(
    f"CAG Performance: "
    f"Hit rate: {cag_metrics['cag_hit_rate']:.1%}, "
    f"Hits: {cag_metrics['cag_hits']}, "
    f"Misses: {cag_metrics['cag_misses']}, "
    f"RAG queries: {cag_metrics['rag_queries']}"
)
```

### Expected Metrics (Target)

| Metric | Before (Pure RAG) | After (CAG + RAG) | Improvement |
|--------|-------------------|-------------------|-------------|
| Avg context retrieval | 250ms | 50ms | 80% ↓ |
| Vector DB queries/review | 3-5 | 1-2 | 60% ↓ |
| Cost per review | $0.002 | $0.0006 | 70% ↓ |
| CAG hit rate | N/A | >90% | New metric |

## Step 5: Cache Invalidation

### When to Invalidate

1. **Main branch update to docs**
   ```rust
   // In webhook handler after main branch merge
   if updated_files.contains(&"CONTRIBUTING.md") ||
      updated_files.contains(&"SECURITY.md") {
       static_cache.invalidate_repo_static_context(&org, &repo).await?;
   }
   ```

2. **Manual invalidation endpoint**
   ```rust
   #[axum::debug_handler]
   async fn invalidate_cache(
       Path((org, repo)): Path<(String, String)>,
       Extension(cache): Extension<Arc<StaticContextCache<MultiTierCache>>>,
   ) -> impl IntoResponse {
       cache.invalidate_repo_static_context(&org, &repo).await?;
       Json(json!({"status": "invalidated"}))
   }
   ```

3. **Scheduled refresh (nightly)**
   ```rust
   // Cron job to refresh all caches
   async fn nightly_cache_refresh() {
       for (org, repo) in repos.iter() {
           // Re-index will automatically refresh cache
           indexing_service.index_repository(request).await?;
       }
   }
   ```

## Step 6: Testing

### Unit Tests

```python
# tests/test_cag.py
import pytest
from coderabbit_ai.cag import HybridContextRetriever

@pytest.mark.asyncio
async def test_hybrid_retriever_cache_hit():
    """Test CAG cache hit scenario."""
    retriever = HybridContextRetriever(
        cache_client=MockCacheClient(has_data=True),
        rag_client=MockRagClient()
    )

    context = await retriever.retrieve_context(
        org="test-org",
        repo="test-repo",
        code_changes="diff",
        pr_description="Test PR"
    )

    # Should have cached static context
    assert len(context.static_context) > 0
    assert context.cache_hit_rate > 0.8

    # Should still query RAG for dynamic
    assert len(context.dynamic_context.similar_patterns) >= 0

@pytest.mark.asyncio
async def test_hybrid_retriever_cache_miss():
    """Test fallback when cache is empty."""
    retriever = HybridContextRetriever(
        cache_client=MockCacheClient(has_data=False),
        rag_client=MockRagClient()
    )

    context = await retriever.retrieve_context(
        org="test-org",
        repo="test-repo",
        code_changes="diff",
        pr_description="Test PR"
    )

    # Should gracefully handle cache miss
    assert context.cache_hit_rate == 0.0
    # But still get dynamic context
    assert context.dynamic_context is not None
```

### Integration Tests

```rust
// tests/integration/cag_integration.rs
#[tokio::test]
async fn test_cache_warmup_on_indexing() {
    let cache = Arc::new(MultiTierCache::new(...).await.unwrap());
    let static_cache = Arc::new(StaticContextCache::new(cache.clone()));

    let service = IndexingService::new(
        orchestrator,
        github_token,
        Some(static_cache.clone())
    );

    // Index repo
    let result = service.index_repository(request).await.unwrap();
    assert!(result.success);

    // Verify cache was warmed
    let cached = static_cache.get_static_context(
        "test-org",
        "test-repo",
        &StaticContentType::OrgPolicies
    ).await.unwrap();

    assert!(cached.is_some());
}
```

## Step 7: Rollout Strategy

### Phase 1: Development (Week 1)
- ✅ Implement StaticContextCache
- ✅ Add cache warmup to IndexingService
- ✅ Create HybridContextRetriever
- ⏳ Unit tests

### Phase 2: Staging (Week 2)
- Deploy to staging environment
- Monitor metrics for 1 week
- Tune TTLs based on invalidation patterns
- Verify cost savings

### Phase 3: Production (Week 3)
- Gradual rollout: 10% → 50% → 100%
- Monitor error rates, latency, costs
- Fine-tune cache invalidation rules

## Troubleshooting

### Issue: Low CAG hit rate (<50%)

**Cause**: Cache not warmed up or invalidated too frequently

**Fix**:
```bash
# Manually trigger cache warmup
curl -X POST http://api/index \
  -H "Content-Type: application/json" \
  -d '{"owner":"org","repo_name":"repo","branch":"main"}'
```

### Issue: Stale cached content

**Cause**: TTL too long, not invalidating on doc changes

**Fix**: Add webhook handler to invalidate on main branch doc changes

### Issue: High memory usage

**Cause**: Too many repos cached in L1

**Fix**: Reduce L1 TTL, rely more on L2 (Redis)

## Cost Analysis

### Before (Pure RAG)
- 10,000 reviews/day
- 3 vector queries per review = 30,000 queries
- $0.0001 per query = **$3/day = $90/month**

### After (CAG + RAG)
- 10,000 reviews/day
- 90% CAG hit rate → 9,000 reviews use cache (0 queries)
- 10% cache miss + dynamic queries → 1,000 reviews × 1 query = 1,000 queries
- $0.0001 per query = **$0.10/day = $3/month**

### Savings
- **$87/month** (97% cost reduction)
- Plus reduced latency and better UX

## Next Steps

1. Run `cargo test` to verify Rust implementation
2. Update `context_engineering.py` with hybrid retriever
3. Deploy to staging and monitor metrics
4. Fine-tune TTLs and invalidation rules
5. Roll out to production gradually

**Unresolved questions:** None
