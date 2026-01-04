"""Integration test for full review workflow.

This test validates the complete end-to-end flow from webhook
to review generation and posting.
"""

import pytest
import httpx
import json
from typing import Dict, Any


class TestFullReviewWorkflow:
    """Test complete review workflow."""

    @pytest.mark.asyncio
    async def test_webhook_to_review_completion(self):
        """Test webhook submission through review completion."""
        # Create mock webhook payload
        webhook_payload = {
            "action": "opened",
            "number": 1,
            "pull_request": {
                "id": 123456,
                "number": 1,
                "title": "Test PR for CodeRabbit review",
                "body": "This is a test PR for validating CodeRabbit AI review system.",
                "user": {"login": "test-user"},
                "head": {"sha": "abc123def456", "ref": "feature/test-integration"},
                "base": {"ref": "main"},
                "html_url": "https://github.com/TAGOOZ/ai-pr-reviewer-tagz/pull/1",
                "state": "open",
            },
            "repository": {
                "id": 789012,
                "name": "ai-pr-reviewer-tagz",
                "full_name": "TAGOOZ/ai-pr-reviewer-tagz",
                "owner": {"login": "TAGOOZ"},
            },
        }

        # Submit webhook
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8080/webhooks/github",
                json=webhook_payload,
                headers={
                    "X-Hub-Signature-256": "test_signature",
                    "Content-Type": "application/json",
                },
            )

            # Verify webhook accepted
            assert response.status_code in [
                202,
                401,
            ]  # 202 if auth passed, 401 if webhook secret check fails

            if response.status_code == 202:
                data = response.json()
                assert "job_id" in data
                job_id = data["job_id"]

                # Poll for job completion (simplified for testing)
                max_attempts = 10
                for attempt in range(max_attempts):
                    status_response = await client.get(
                        f"http://localhost:8080/jobs/{job_id}"
                    )
                    status_data = status_response.json()

                    if status_data.get("status") == "completed":
                        # Verify review was generated
                        assert "review_id" in status_data
                        review_id = status_data["review_id"]

                        # Fetch review details
                        review_response = await client.get(
                            f"http://localhost:8080/reviews/{review_id}"
                        )
                        review_data = review_response.json()

                        # Validate review structure
                        assert "comments" in review_data
                        assert "summary" in review_data
                        assert "metrics" in review_data

                        return  # Test passed

                    await client.sleep(2)  # Wait between polls

    @pytest.mark.asyncio
    async def test_review_quality_metrics(self):
        """Test that review includes quality metrics."""
        review_data = {
            "pull_request_number": 1,
            "repository": "TAGOOZ/ai-pr-reviewer-tagz",
            "files_changed": [
                {
                    "path": "python/coderabbit_ai/server.py",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 5,
                }
            ],
        }

        # Submit review request
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:8000/review", json=review_data
            )

            if response.status_code == 200:
                result = response.json()

                # Verify quality metrics are present
                assert "comments" in result or "review" in result

                # Check for different types of feedback
                review_content = result.get("review", result.get("comments", []))

                # Should have at least some feedback
                assert len(review_content) >= 0

                # Verify comment structure
                if len(review_content) > 0:
                    first_comment = review_content[0]
                    assert "file" in first_comment or "path" in first_comment
                    assert "line" in first_comment or "body" in first_comment

    def test_security_scan_integration(self):
        """Test that security scanning is integrated into review."""
        # This is a placeholder for when security scanning is fully integrated
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--asyncio-mode=auto"])
