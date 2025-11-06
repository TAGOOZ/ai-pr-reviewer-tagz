"""Hybrid Context Retriever combining CAG (cached) and RAG (dynamic) contexts."""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Static content types for CAG layer."""
    ORG_POLICIES = "policies"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    STYLE_GUIDES = "style_guides"
    BEST_PRACTICES = "best_practices"


@dataclass
class StaticContext:
    """Static context from CAG layer."""
    content_type: ContentType
    content: str
    source_files: List[str]
    org: str
    repo: str
    cached: bool = True  # Always true for CAG


@dataclass
class DynamicContext:
    """Dynamic context from RAG layer."""
    similar_patterns: List[Dict[str, Any]]
    related_issues: List[Dict[str, Any]]
    code_smells: List[Dict[str, Any]]
    cached: bool = False  # Always false for RAG


@dataclass
class HybridContext:
    """Combined context from CAG + RAG."""
    static_context: Dict[ContentType, StaticContext]
    dynamic_context: DynamicContext
    total_retrieval_time_ms: int
    cache_hit_rate: float


class HybridContextRetriever:
    """
    Retrieves context using hybrid CAG + RAG approach.

    CAG (Cache-Augmented Generation):
    - Fetches static content from cache (org policies, architecture, etc.)
    - 0ms retrieval time for cached content
    - No vector DB queries for static content

    RAG (Retrieval-Augmented Generation):
    - Fetches dynamic content from vector DB (recent patterns, issues)
    - Necessary queries only for fresh, PR-specific context
    """

    def __init__(self, cache_client: Optional[Any] = None, rag_client: Optional[Any] = None):
        """
        Initialize hybrid retriever.

        Args:
            cache_client: Client for CAG layer (Redis/MultiTierCache)
            rag_client: Client for RAG layer (VectorEngine/LanceDB)
        """
        self.cache_client = cache_client
        self.rag_client = rag_client
        self.metrics = {
            "cag_hits": 0,
            "cag_misses": 0,
            "rag_queries": 0,
            "avg_cag_time_ms": 0,
            "avg_rag_time_ms": 0,
        }

    async def retrieve_context(
        self,
        org: str,
        repo: str,
        code_changes: str,
        pr_description: str,
    ) -> HybridContext:
        """
        Retrieve hybrid context using CAG + RAG.

        Strategy:
        1. Try CAG first for static content (fast, no cost)
        2. Use RAG for dynamic content (necessary queries only)
        3. Combine both contexts

        Args:
            org: Organization name
            repo: Repository name
            code_changes: PR code changes for dynamic context
            pr_description: PR description for context

        Returns:
            HybridContext with both static and dynamic content
        """
        import time
        start_time = time.time()

        # Step 1: Get static context from CAG (cache)
        static_context = await self._get_static_context_from_cache(org, repo)

        # Step 2: Get dynamic context from RAG (vector DB)
        dynamic_context = await self._get_dynamic_context_from_rag(
            org, repo, code_changes, pr_description
        )

        total_time = int((time.time() - start_time) * 1000)

        # Calculate cache hit rate
        total_types = len(ContentType)
        cache_hits = len(static_context)
        cache_hit_rate = cache_hits / total_types if total_types > 0 else 0.0

        logger.info(
            f"Hybrid context retrieval for {org}/{repo}: "
            f"{cache_hits}/{total_types} CAG hits, "
            f"RAG query completed in {total_time}ms"
        )

        return HybridContext(
            static_context=static_context,
            dynamic_context=dynamic_context,
            total_retrieval_time_ms=total_time,
            cache_hit_rate=cache_hit_rate,
        )

    async def _get_static_context_from_cache(
        self,
        org: str,
        repo: str,
    ) -> Dict[ContentType, StaticContext]:
        """
        Get static context from CAG layer (cache).

        This is the key optimization:
        - No vector DB queries
        - No embedding computation
        - Instant retrieval from cache
        - Works for ~70% of context needs
        """
        static_context = {}

        if not self.cache_client:
            logger.warning("CAG cache client not available, skipping static context")
            return static_context

        import time

        for content_type in ContentType:
            cache_key = f"static_context:{org}:{repo}:{content_type.value}"

            start = time.time()
            try:
                cached_content = await self._get_from_cache(cache_key)

                if cached_content:
                    static_context[content_type] = StaticContext(
                        content_type=content_type,
                        content=cached_content.get("content", ""),
                        source_files=cached_content.get("source_files", []),
                        org=org,
                        repo=repo,
                        cached=True,
                    )
                    self.metrics["cag_hits"] += 1

                    elapsed_ms = int((time.time() - start) * 1000)
                    logger.debug(f"CAG hit for {content_type.value}: {elapsed_ms}ms")
                else:
                    self.metrics["cag_misses"] += 1
                    logger.debug(f"CAG miss for {content_type.value}")

            except Exception as e:
                logger.warning(f"CAG retrieval failed for {content_type.value}: {e}")
                self.metrics["cag_misses"] += 1

        return static_context

    async def _get_dynamic_context_from_rag(
        self,
        org: str,
        repo: str,
        code_changes: str,
        pr_description: str,
    ) -> DynamicContext:
        """
        Get dynamic context from RAG layer (vector DB).

        This query is necessary because:
        - Similar patterns change with every new PR
        - Related issues are PR-specific
        - Code smells depend on current code changes
        """
        if not self.rag_client:
            logger.warning("RAG client not available, returning empty dynamic context")
            return DynamicContext(
                similar_patterns=[],
                related_issues=[],
                code_smells=[],
                cached=False,
            )

        import time
        start = time.time()

        try:
            # Query vector DB for dynamic content only
            rag_result = await self._query_vector_db(
                code_changes=code_changes,
                pr_description=pr_description,
                last_n_days=90,  # Only recent patterns matter
            )

            self.metrics["rag_queries"] += 1
            elapsed_ms = int((time.time() - start) * 1000)

            logger.info(
                f"RAG query completed in {elapsed_ms}ms: "
                f"{len(rag_result.get('similar_patterns', []))} patterns, "
                f"{len(rag_result.get('related_issues', []))} issues"
            )

            return DynamicContext(
                similar_patterns=rag_result.get("similar_patterns", []),
                related_issues=rag_result.get("related_issues", []),
                code_smells=rag_result.get("code_smells", []),
                cached=False,
            )

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return DynamicContext(
                similar_patterns=[],
                related_issues=[],
                code_smells=[],
                cached=False,
            )

    async def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get content from cache (abstracted for testing)."""
        # This would call the actual cache client
        # For now, return None to simulate cache miss
        # In production, this calls: self.cache_client.get(cache_key)
        return None

    async def _query_vector_db(
        self,
        code_changes: str,
        pr_description: str,
        last_n_days: int = 90,
    ) -> Dict[str, Any]:
        """Query vector DB for dynamic context (abstracted for testing)."""
        # This would call the actual RAG client
        # For now, return empty results
        # In production, this calls: self.rag_client.hybrid_search(...)
        return {
            "similar_patterns": [],
            "related_issues": [],
            "code_smells": [],
        }

    def format_hybrid_context(self, hybrid_context: HybridContext) -> str:
        """
        Format hybrid context for DSPy agents.

        Structure:
        === STATIC CONTEXT (from CAG) ===
        [Org policies, architecture, security, etc.]

        === DYNAMIC CONTEXT (from RAG) ===
        [Recent patterns, issues, code smells]
        """
        sections = []

        # Format static context
        if hybrid_context.static_context:
            sections.append("=== STATIC CONTEXT (Cached from CAG) ===\n")

            for content_type, static_ctx in hybrid_context.static_context.items():
                sections.append(f"## {content_type.value.upper().replace('_', ' ')}")
                sections.append(f"Sources: {', '.join(static_ctx.source_files)}")
                sections.append(f"{static_ctx.content[:1000]}...\n")  # Truncate for context window

        # Format dynamic context
        sections.append("\n=== DYNAMIC CONTEXT (from RAG) ===\n")

        if hybrid_context.dynamic_context.similar_patterns:
            sections.append(f"## Similar Patterns ({len(hybrid_context.dynamic_context.similar_patterns)})")
            for pattern in hybrid_context.dynamic_context.similar_patterns[:5]:
                sections.append(f"- {pattern}")

        if hybrid_context.dynamic_context.related_issues:
            sections.append(f"\n## Related Issues ({len(hybrid_context.dynamic_context.related_issues)})")
            for issue in hybrid_context.dynamic_context.related_issues[:3]:
                sections.append(f"- {issue}")

        # Add metadata
        sections.append(
            f"\n[Context Stats: {len(hybrid_context.static_context)} static types cached, "
            f"cache hit rate: {hybrid_context.cache_hit_rate:.1%}, "
            f"retrieval time: {hybrid_context.total_retrieval_time_ms}ms]"
        )

        return "\n".join(sections)

    def get_metrics(self) -> Dict[str, Any]:
        """Get retrieval metrics for monitoring."""
        total_cag = self.metrics["cag_hits"] + self.metrics["cag_misses"]
        cag_hit_rate = self.metrics["cag_hits"] / total_cag if total_cag > 0 else 0.0

        return {
            "cag_hit_rate": cag_hit_rate,
            "cag_hits": self.metrics["cag_hits"],
            "cag_misses": self.metrics["cag_misses"],
            "rag_queries": self.metrics["rag_queries"],
            "avg_cag_time_ms": self.metrics["avg_cag_time_ms"],
            "avg_rag_time_ms": self.metrics["avg_rag_time_ms"],
        }
