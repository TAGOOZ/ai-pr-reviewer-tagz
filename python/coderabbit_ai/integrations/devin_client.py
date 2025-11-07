"""Devin API client for private repository indexing with DeepWiki."""

import logging
from typing import Dict, Optional, Any
from enum import Enum
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class IndexingStatus(str, Enum):
    """Status of repository indexing."""
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DevinClient:
    """
    Client for Devin API integration.

    Devin (by Cognition AI) can index private repositories for DeepWiki
    access. This client handles requesting indexing and checking status.

    Note: Requires Devin account and API key for private repo access.
    Public repos in DeepWiki's 50k index don't need this.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = "https://api.devin.ai",
        timeout: int = 30
    ):
        """
        Initialize Devin client.

        Args:
            api_key: Devin API key (required for private repos)
            api_url: Devin API base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.enabled = api_key is not None

        if not self.enabled:
            logger.warning(
                "Devin API key not provided. Private repo indexing disabled. "
                "Set DEVIN_API_KEY environment variable to enable."
            )
        else:
            logger.info("Devin client initialized")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated request to Devin API."""
        if not self.enabled:
            logger.error("Devin client not enabled (no API key)")
            return None

        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            if method.upper() == "POST":
                response = requests.post(
                    url,
                    json=json_data,
                    headers=headers,
                    timeout=self.timeout
                )
            elif method.upper() == "GET":
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            if response.status_code in [200, 201, 202]:
                return response.json()
            elif response.status_code == 401:
                logger.error("Devin API authentication failed. Check API key.")
                return None
            elif response.status_code == 404:
                logger.warning(f"Devin API endpoint not found: {endpoint}")
                return None
            else:
                logger.error(
                    f"Devin API request failed: {response.status_code} - {response.text[:200]}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Devin API request timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Devin API request failed: {e}")
            return None

    def request_indexing(
        self,
        repo: str,
        priority: str = "normal"
    ) -> Optional[Dict[str, Any]]:
        """
        Request Devin to index a private repository for DeepWiki.

        This queues the repository for indexing. Indexing typically
        takes several hours depending on repository size and queue.

        Args:
            repo: Repository in format "owner/name"
            priority: Priority level ("low", "normal", "high")

        Returns:
            Dict with indexing request details or None if failed
            {
                "request_id": "req_abc123",
                "repository": "owner/repo",
                "status": "queued",
                "estimated_time": "2-4 hours",
                "created_at": "2025-11-07T10:30:00Z"
            }

        Example:
            >>> client = DevinClient(api_key="sk-...")
            >>> result = client.request_indexing("myorg/private-repo")
            >>> if result:
            ...     print(f"Indexing requested: {result['request_id']}")
        """
        if not self.enabled:
            return None

        logger.info(f"Requesting Devin indexing for {repo} (priority: {priority})")

        result = self._make_request(
            "POST",
            "/deepwiki/index",
            json_data={
                "repository": repo,
                "priority": priority,
                "timestamp": datetime.now().isoformat()
            }
        )

        if result:
            logger.info(
                f"Indexing requested successfully for {repo}. "
                f"Request ID: {result.get('request_id', 'unknown')}"
            )
        else:
            logger.error(f"Failed to request indexing for {repo}")

        return result

    def check_indexing_status(self, repo: str) -> IndexingStatus:
        """
        Check indexing status for a repository.

        Args:
            repo: Repository in format "owner/name"

        Returns:
            IndexingStatus enum value

        Example:
            >>> status = client.check_indexing_status("myorg/private-repo")
            >>> if status == IndexingStatus.COMPLETED:
            ...     print("Repository is indexed and ready!")
        """
        if not self.enabled:
            return IndexingStatus.UNKNOWN

        logger.debug(f"Checking indexing status for {repo}")

        result = self._make_request(
            "GET",
            f"/deepwiki/index/status?repository={repo}"
        )

        if not result:
            return IndexingStatus.UNKNOWN

        status_str = result.get("status", "unknown").lower()

        try:
            status = IndexingStatus(status_str)
            logger.debug(f"Indexing status for {repo}: {status.value}")
            return status
        except ValueError:
            logger.warning(f"Unknown indexing status: {status_str}")
            return IndexingStatus.UNKNOWN

    def get_indexing_details(self, repo: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed indexing information.

        Args:
            repo: Repository in format "owner/name"

        Returns:
            Dict with detailed indexing info or None

        Example:
            >>> details = client.get_indexing_details("myorg/private-repo")
            >>> if details:
            ...     print(f"Progress: {details['progress_percent']}%")
            ...     print(f"ETA: {details['estimated_completion']}")
        """
        if not self.enabled:
            return None

        result = self._make_request(
            "GET",
            f"/deepwiki/index/details?repository={repo}"
        )

        return result

    def cancel_indexing(self, repo: str) -> bool:
        """
        Cancel pending indexing request.

        Args:
            repo: Repository in format "owner/name"

        Returns:
            True if cancellation successful
        """
        if not self.enabled:
            return False

        logger.info(f"Canceling indexing for {repo}")

        result = self._make_request(
            "POST",
            "/deepwiki/index/cancel",
            json_data={"repository": repo}
        )

        success = result is not None and result.get("status") == "cancelled"

        if success:
            logger.info(f"Indexing cancelled for {repo}")
        else:
            logger.error(f"Failed to cancel indexing for {repo}")

        return success

    def list_indexed_repos(self) -> Optional[List[str]]:
        """
        List all repositories indexed via Devin account.

        Returns:
            List of repository names or None if failed

        Example:
            >>> repos = client.list_indexed_repos()
            >>> print(f"You have {len(repos)} private repos indexed")
        """
        if not self.enabled:
            return None

        result = self._make_request("GET", "/deepwiki/index/list")

        if result and "repositories" in result:
            return result["repositories"]

        return None

    def auto_request_if_needed(
        self,
        repo: str,
        auto_request: bool = False
    ) -> Dict[str, Any]:
        """
        Check if repo needs indexing and optionally request it.

        This is a convenience method that combines status checking
        with automatic request submission.

        Args:
            repo: Repository in format "owner/name"
            auto_request: Automatically request indexing if needed

        Returns:
            Dict with status and action taken:
            {
                "status": IndexingStatus,
                "action": "none"|"requested"|"already_indexed",
                "needs_wait": bool,
                "message": str
            }

        Example:
            >>> result = client.auto_request_if_needed(
            ...     "myorg/private-repo",
            ...     auto_request=True
            ... )
            >>> print(result['message'])
            "Indexing requested. Please wait 2-4 hours."
        """
        if not self.enabled:
            return {
                "status": IndexingStatus.UNKNOWN,
                "action": "none",
                "needs_wait": False,
                "message": "Devin integration not enabled (no API key)"
            }

        # Check current status
        status = self.check_indexing_status(repo)

        if status == IndexingStatus.COMPLETED:
            return {
                "status": status,
                "action": "already_indexed",
                "needs_wait": False,
                "message": f"Repository {repo} is already indexed"
            }

        elif status in [IndexingStatus.QUEUED, IndexingStatus.IN_PROGRESS]:
            return {
                "status": status,
                "action": "none",
                "needs_wait": True,
                "message": f"Indexing {status.value}. Please wait."
            }

        elif status in [IndexingStatus.NOT_STARTED, IndexingStatus.FAILED, IndexingStatus.UNKNOWN]:
            if auto_request:
                logger.info(f"Auto-requesting indexing for {repo}")
                request_result = self.request_indexing(repo)

                if request_result:
                    return {
                        "status": IndexingStatus.QUEUED,
                        "action": "requested",
                        "needs_wait": True,
                        "message": (
                            f"Indexing requested for {repo}. "
                            f"Estimated time: 2-4 hours. "
                            f"Request ID: {request_result.get('request_id', 'unknown')}"
                        )
                    }
                else:
                    return {
                        "status": status,
                        "action": "failed",
                        "needs_wait": False,
                        "message": f"Failed to request indexing for {repo}"
                    }
            else:
                return {
                    "status": status,
                    "action": "none",
                    "needs_wait": False,
                    "message": (
                        f"Repository {repo} not indexed. "
                        f"Call request_indexing() to queue for indexing."
                    )
                }

        return {
            "status": status,
            "action": "none",
            "needs_wait": False,
            "message": f"Unknown status: {status.value}"
        }
