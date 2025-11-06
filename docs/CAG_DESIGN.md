# Cache-Augmented Generation (CAG) Design

## Problem Statement

Current RAG implementation queries vector database for every PR review, including static content that rarely changes:
- Organization coding standards
- Architecture documentation
- Security best practices
- Style guides

**Cost**: Every query = vector DB hit + embedding computation
**Latency**: 100-300ms per RAG query
**Waste**: 70% of retrieved content is static (unchanged for weeks/months)

## Solution: RAG + CAG Hybrid

Split knowledge into two layers:

### Layer 1: CAG (Static Context Cache)
**What to cache:**
- Org coding standards (CONTRIBUTING.md, CODE_STYLE.md)
- Architecture patterns (ARCHITECTURE.md, DESIGN.md)
- Security policies (SECURITY.md, security requirements)
- Project conventions (README.md sections about conventions)
- Language style guides

**Cache strategy:**
- Embed once at repo indexing time
- Store in L1 (in-memory) + L2 (Redis) cache
- TTL: 24 hours (refreshed nightly)
- Invalidate on: main branch changes to these files

**Key format:**
```
static_context:{org}:{repo}:{file_type}
```

**Benefits:**
- 0ms retrieval (already in memory)
- No vector DB queries
- No embedding computation
- Reduced costs by ~70%

### Layer 2: RAG (Dynamic Context Retrieval)
**What to retrieve:**
- Recent similar code patterns
- Recent related issues/PRs
- New code smells
- Dynamic code relationships

**Query strategy:**
- Vector search on demand
- Hybrid search (vector + keyword)
- Limited to last N days of changes

**Key insight:** Dynamic content changes per PR, must be retrieved fresh

## Architecture

```
PR Review Request
       ↓
Context Engineering Agent
       ↓
   ┌───────────────┐
   │ CAG Layer     │ → Check cache for static context
   │ (L1/L2 Cache) │    - Org policies
   │               │    - Architecture docs
   │               │    - Best practices
   └───────────────┘
         ↓ (if cached: 0ms, else: warmup)
   ┌───────────────┐
   │ RAG Layer     │ → Query vector DB for dynamic content
   │ (LanceDB)     │    - Similar code patterns (recent)
   │               │    - Related issues (last 90 days)
   │               │    - Code smells
   └───────────────┘
         ↓
   Combined Context → Verification Agents
```

## Implementation Plan

### 1. Create StaticContextCache Module
```rust
pub struct StaticContextCache {
    cache: Arc<MultiTierCache>,
    static_content_types: Vec<StaticContentType>,
}

pub enum StaticContentType {
    OrgPolicies,      // Coding standards, conventions
    Architecture,     // Design docs, patterns
    Security,         // Security policies, requirements
    StyleGuides,      // Language-specific style guides
    BestPractices,    // General best practices
}
```

### 2. Cache Warmup Service
- Triggered on repo indexing
- Extracts static content from docs
- Caches with 24h TTL
- Runs nightly refresh job

### 3. Smart Context Retrieval
```python
class HybridContextRetriever:
    def retrieve_context(self, pr_data):
        # CAG: Get static context from cache
        static_context = self.get_cached_static_context(pr_data.org, pr_data.repo)

        # RAG: Get dynamic context from vector DB
        dynamic_context = self.query_vector_db(pr_data.code_changes, last_n_days=90)

        return CombinedContext(
            static=static_context,
            dynamic=dynamic_context
        )
```

### 4. Cache Invalidation Strategy
**Invalidate static cache when:**
- Main branch updates to docs
- Manual org policy updates
- Scheduled refresh (nightly)

**Never invalidate:**
- On PR branches
- On feature development

## Expected Performance Gains

**Before (Pure RAG):**
- Avg query time: 250ms
- Vector DB queries per review: 3-5
- Cost per review: $0.002 (embeddings + search)

**After (RAG + CAG):**
- Avg query time: 50ms (80% reduction)
- Vector DB queries per review: 1-2 (60% reduction)
- Cost per review: $0.0006 (70% reduction)

**At scale (10k reviews/day):**
- Time saved: 33 minutes/day
- Cost saved: $14/day = $420/month

## Content Classification

| Content Type | Layer | TTL | Update Frequency |
|--------------|-------|-----|------------------|
| Org coding standards | CAG | 24h | Weekly |
| Architecture docs | CAG | 24h | Monthly |
| Security policies | CAG | 12h | Weekly |
| Style guides | CAG | 24h | Rarely |
| Recent code patterns | RAG | N/A | Every PR |
| Related issues | RAG | N/A | Every PR |
| Code smells | RAG | N/A | Every PR |
| Dynamic relationships | RAG | N/A | Every PR |

## Cache Key Design

```
# Static context keys (CAG)
static_context:{org}:{repo}:policies
static_context:{org}:{repo}:architecture
static_context:{org}:{repo}:security
static_context:{org}:{repo}:style_guides
static_context:{org}:{repo}:best_practices

# Dynamic context queries (RAG)
rag_query:{hash(code_changes)}:{timestamp}
```

## Monitoring Metrics

Track:
- CAG hit rate (target: >90%)
- RAG query reduction (target: 60%)
- Avg context retrieval time (target: <100ms)
- Cost per review (target: <$0.001)
- Cache memory usage (target: <500MB per repo)

## Rollout Plan

1. Implement StaticContextCache module
2. Add cache warmup on indexing
3. Update context_engineering.py to check cache first
4. Monitor metrics for 1 week
5. Tune TTLs based on invalidation patterns
6. Roll out to all repos

## Trade-offs

**Pros:**
- 70% cost reduction
- 80% latency reduction
- Better performance at scale

**Cons:**
- Slight staleness (max 24h) for static content
- Additional cache memory (500MB per repo)
- Cache warmup complexity

**Mitigation:**
- Manual cache invalidation endpoint for urgent policy updates
- Configurable TTLs per content type
- Fallback to RAG if cache miss
