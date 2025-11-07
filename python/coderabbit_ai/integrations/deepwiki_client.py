"""DeepWiki MCP client for semantic repository documentation."""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class DeepWikiContext:
    """Context enriched with DeepWiki semantic documentation."""

    repo: str
    architectural_overview: Optional[str]
    component_relationships: Dict[str, Any]
    relevant_documentation: List[str]
    patterns_and_conventions: List[str]
    timestamp: datetime

    def is_fresh(self, ttl_seconds: int = 3600) -> bool:
        """Check if context is still fresh based on TTL."""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age < ttl_seconds


class DeepWikiClient:
    """
    Client for DeepWiki MCP server integration.

    DeepWiki provides AI-generated semantic documentation for 50k+
    public GitHub repositories. This client interfaces with their
    MCP (Model Context Protocol) server to retrieve architectural
    context for code review.

    Features:
    - Semantic Q&A about repository architecture
    - Documentation structure navigation
    - Component relationship mapping
    - Pattern and convention discovery
    - Caching with configurable TTL
    - Automatic retry with exponential backoff
    """

    def __init__(
        self,
        mcp_url: str = "https://mcp.deepwiki.com/mcp",
        sse_url: str = "https://mcp.deepwiki.com/sse",
        timeout: int = 30,
        cache_ttl: int = 3600,
        max_retries: int = 3,
    ):
        """
        Initialize DeepWiki client.

        Args:
            mcp_url: MCP endpoint URL
            sse_url: Server-Sent Events endpoint URL
            timeout: Request timeout in seconds
            cache_ttl: Cache time-to-live in seconds
            max_retries: Maximum number of retry attempts
        """
        self.mcp_url = mcp_url
        self.sse_url = sse_url
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries

        # In-memory cache: {cache_key: (data, timestamp)}
        self._cache: Dict[str, tuple[Any, datetime]] = {}

        # Configure session with retry logic
        self.session = self._create_session()

        logger.info(f"DeepWiki client initialized: {mcp_url}")

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached value if fresh."""
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            age = (datetime.now() - timestamp).total_seconds()
            if age < self.cache_ttl:
                logger.debug(f"Cache hit: {cache_key} (age: {age:.1f}s)")
                return data
            else:
                # Expired
                logger.debug(f"Cache expired: {cache_key}")
                del self._cache[cache_key]
        return None

    def _set_cached(self, cache_key: str, data: Any) -> None:
        """Store value in cache with timestamp."""
        self._cache[cache_key] = (data, datetime.now())
        logger.debug(f"Cache set: {cache_key}")

    def is_repo_indexed(self, repo: str) -> bool:
        """
        Check if repository is indexed in DeepWiki.

        Args:
            repo: Repository in format "owner/name"

        Returns:
            True if repo is indexed and available
        """
        cache_key = f"indexed:{repo}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            # Try to get wiki structure as a quick check
            structure = self.read_wiki_structure(repo)
            is_indexed = structure is not None
            self._set_cached(cache_key, is_indexed)
            return is_indexed
        except Exception as e:
            logger.warning(f"Failed to check if {repo} is indexed: {e}")
            return False

    def ask_question(
        self,
        repo: str,
        question: str,
        use_cache: bool = True
    ) -> Optional[str]:
        """
        Ask natural language question about repository.

        This is the most flexible way to get information from DeepWiki.
        It uses AI to answer questions about architecture, patterns,
        dependencies, and conventions.

        Args:
            repo: Repository in format "owner/name"
            question: Natural language question
            use_cache: Use cached response if available

        Returns:
            Answer string or None if failed

        Example:
            >>> client.ask_question(
            ...     "facebook/react",
            ...     "What is the reconciliation algorithm?"
            ... )
            "The reconciliation algorithm is React's diffing algorithm..."
        """
        cache_key = f"q:{repo}:{question}"

        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        try:
            logger.info(f"Asking DeepWiki: {repo} - {question[:50]}...")

            response = self.session.post(
                f"{self.mcp_url}/ask_question",
                json={
                    "repository": repo,
                    "question": question
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer")

                if answer:
                    self._set_cached(cache_key, answer)
                    logger.info(f"DeepWiki answered successfully")
                    return answer
                else:
                    logger.warning(f"DeepWiki returned empty answer")
                    return None

            elif response.status_code == 404:
                logger.warning(f"Repository {repo} not found in DeepWiki")
                return None

            else:
                logger.warning(
                    f"DeepWiki question failed: {response.status_code} - {response.text[:200]}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"DeepWiki request timed out after {self.timeout}s")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"DeepWiki request failed: {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in ask_question: {e}")
            return None

    def read_wiki_structure(
        self,
        repo: str,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get repository documentation structure.

        Returns the hierarchical organization of documentation,
        including sections, pages, and topics.

        Args:
            repo: Repository in format "owner/name"
            use_cache: Use cached response if available

        Returns:
            Structure dict with sections and pages, or None if failed

        Example:
            >>> structure = client.read_wiki_structure("facebook/react")
            >>> print(structure.keys())
            dict_keys(['sections', 'pages', 'overview'])
        """
        cache_key = f"structure:{repo}"

        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        try:
            logger.info(f"Fetching wiki structure for {repo}")

            response = self.session.post(
                f"{self.mcp_url}/read_wiki_structure",
                json={"repository": repo},
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                structure = data.get("structure")

                if structure:
                    self._set_cached(cache_key, structure)
                    logger.info(f"Wiki structure retrieved successfully")
                    return structure
                else:
                    logger.warning(f"DeepWiki returned empty structure")
                    return None

            elif response.status_code == 404:
                logger.warning(f"Repository {repo} not found in DeepWiki")
                return None

            else:
                logger.warning(
                    f"DeepWiki structure request failed: {response.status_code}"
                )
                return None

        except Exception as e:
            logger.error(f"Error reading wiki structure: {e}")
            return None

    def read_wiki_contents(
        self,
        repo: str,
        page: str,
        use_cache: bool = True
    ) -> Optional[str]:
        """
        Read specific wiki page content.

        Args:
            repo: Repository in format "owner/name"
            page: Page identifier from wiki structure
            use_cache: Use cached response if available

        Returns:
            Page content (markdown) or None if failed

        Example:
            >>> content = client.read_wiki_contents(
            ...     "facebook/react",
            ...     "architecture/reconciliation"
            ... )
        """
        cache_key = f"page:{repo}:{page}"

        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        try:
            logger.info(f"Fetching wiki page: {repo}/{page}")

            response = self.session.post(
                f"{self.mcp_url}/read_wiki_contents",
                json={
                    "repository": repo,
                    "page": page
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                content = data.get("content")

                if content:
                    self._set_cached(cache_key, content)
                    logger.info(f"Wiki page retrieved successfully")
                    return content
                else:
                    logger.warning(f"DeepWiki returned empty content")
                    return None

            else:
                logger.warning(
                    f"DeepWiki content request failed: {response.status_code}"
                )
                return None

        except Exception as e:
            logger.error(f"Error reading wiki contents: {e}")
            return None

    def get_component_relationships(
        self,
        repo: str,
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get semantic relationships for a specific file/component.

        Args:
            repo: Repository in format "owner/name"
            file_path: Path to file in repository

        Returns:
            Dict with dependencies, dependents, and related docs

        Example:
            >>> rels = client.get_component_relationships(
            ...     "facebook/react",
            ...     "packages/react-reconciler/src/ReactFiber.js"
            ... )
            >>> print(rels['dependencies'])
        """
        question = (
            f"What are the dependencies and relationships for {file_path}? "
            f"Include which components depend on it and which it depends on. "
            f"Also mention any related documentation or patterns."
        )

        answer = self.ask_question(repo, question)

        if not answer:
            return None

        return {
            "file_path": file_path,
            "raw_answer": answer,
            "timestamp": datetime.now().isoformat(),
            # TODO: Could use LLM to parse into structured format
        }

    def enrich_pr_context(
        self,
        repo: str,
        changed_files: List[str],
        pr_description: Optional[str] = None
    ) -> DeepWikiContext:
        """
        Enrich PR review context with DeepWiki information.

        This is the main method for integrating DeepWiki into the
        review pipeline. It queries DeepWiki about the changed files
        and returns structured context.

        Args:
            repo: Repository in format "owner/name"
            changed_files: List of files being modified
            pr_description: Optional PR description for context

        Returns:
            DeepWikiContext with enriched information

        Example:
            >>> context = client.enrich_pr_context(
            ...     "facebook/react",
            ...     ["packages/react/src/React.js"],
            ...     "Add new hook API"
            ... )
            >>> print(context.architectural_overview)
        """
        logger.info(f"Enriching PR context for {repo} ({len(changed_files)} files)")

        # Get architectural overview
        overview_question = (
            f"Provide a brief architectural overview of the components "
            f"involved in these files: {', '.join(changed_files[:5])}."
        )
        architectural_overview = self.ask_question(repo, overview_question)

        # Get component relationships
        component_relationships = {}
        for file_path in changed_files[:3]:  # Limit to first 3 for performance
            rels = self.get_component_relationships(repo, file_path)
            if rels:
                component_relationships[file_path] = rels

        # Get patterns and conventions
        patterns_question = (
            f"What are the coding patterns and conventions used in this repository, "
            f"particularly relevant to: {', '.join(changed_files[:3])}?"
        )
        patterns_answer = self.ask_question(repo, patterns_question)
        patterns_and_conventions = [patterns_answer] if patterns_answer else []

        # Try to get relevant documentation
        structure = self.read_wiki_structure(repo)
        relevant_documentation = []
        if structure and "pages" in structure:
            # Extract page titles (simplified)
            relevant_documentation = structure.get("pages", [])[:5]

        return DeepWikiContext(
            repo=repo,
            architectural_overview=architectural_overview,
            component_relationships=component_relationships,
            relevant_documentation=relevant_documentation,
            patterns_and_conventions=patterns_and_conventions,
            timestamp=datetime.now()
        )

    def format_for_llm(self, context: DeepWikiContext) -> str:
        """
        Format DeepWiki context for LLM consumption.

        Args:
            context: DeepWikiContext to format

        Returns:
            Formatted markdown string
        """
        lines = [
            "## DeepWiki Semantic Context",
            "",
            f"**Repository**: {context.repo}",
            "",
        ]

        if context.architectural_overview:
            lines.extend([
                "### Architectural Overview",
                "",
                context.architectural_overview,
                "",
            ])

        if context.component_relationships:
            lines.extend([
                "### Component Relationships",
                "",
            ])
            for file_path, rels in context.component_relationships.items():
                lines.append(f"**{file_path}**:")
                lines.append(rels.get("raw_answer", "No information available"))
                lines.append("")

        if context.patterns_and_conventions:
            lines.extend([
                "### Patterns & Conventions",
                "",
            ])
            for pattern in context.patterns_and_conventions:
                lines.append(f"- {pattern}")
            lines.append("")

        if context.relevant_documentation:
            lines.extend([
                "### Relevant Documentation",
                "",
            ])
            for doc in context.relevant_documentation[:5]:
                lines.append(f"- {doc}")
            lines.append("")

        lines.append(f"*Context retrieved: {context.timestamp.strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.info("DeepWiki cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_items = len(self._cache)
        fresh_items = sum(
            1 for _, (_, timestamp) in self._cache.items()
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl
        )

        return {
            "total_items": total_items,
            "fresh_items": fresh_items,
            "expired_items": total_items - fresh_items,
            "cache_ttl": self.cache_ttl
        }
