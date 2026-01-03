"""Unit tests for devin_client.py."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import Timeout

from coderabbit_ai.integrations.devin_client import (
    DevinClient,
    IndexingStatus
)


class TestDevinClientInit:
    """Test DevinClient initialization."""

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        client = DevinClient(api_key="test_api_key")

        assert client.api_key == "test_api_key"
        assert client.api_url == "https://api.devin.ai"
        assert client.timeout == 30
        assert client.enabled == True

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        client = DevinClient(api_key=None)

        assert client.api_key is None
        assert client.enabled == False

    def test_init_with_custom_url(self):
        """Test initialization with custom API URL."""
        client = DevinClient(
            api_key="test_key",
            api_url="https://custom.api.com/v1/"
        )

        assert client.api_url == "https://custom.api.com/v1"

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        client = DevinClient(
            api_key="test_key",
            timeout=60
        )

        assert client.timeout == 60


class TestMakeRequest:
    """Test _make_request method."""

    @patch('coderabbit_ai.integrations.devin_client.requests.post')
    def test_post_request_success(self, mock_post):
        """Test successful POST request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_response

        client = DevinClient(api_key="test_key")
        result = client._make_request("POST", "/test", {"data": "test"})

        assert result == {"status": "ok"}
        mock_post.assert_called_once()

    @patch('coderabbit_ai.integrations.devin_client.requests.get')
    def test_get_request_success(self, mock_get):
        """Test successful GET request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response

        client = DevinClient(api_key="test_key")
        result = client._make_request("GET", "/test")

        assert result == {"status": "ok"}
        mock_get.assert_called_once()

    def test_request_without_api_key(self, caplog):
        """Test request without API key returns None."""
        client = DevinClient(api_key=None)
        result = client._make_request("GET", "/test")

        assert result is None
        assert "Devin client not enabled" in caplog.text

    @patch('coderabbit_ai.integrations.devin_client.requests.post')
    def test_post_request_201(self, mock_post):
        """Test POST request with 201 status."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"created": True}
        mock_post.return_value = mock_response

        client = DevinClient(api_key="test_key")
        result = client._make_request("POST", "/test")

        assert result == {"created": True}

    @patch('coderabbit_ai.integrations.devin_client.requests.post')
    def test_post_request_202(self, mock_post):
        """Test POST request with 202 status."""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"queued": True}
        mock_post.return_value = mock_response

        client = DevinClient(api_key="test_key")
        result = client._make_request("POST", "/test")

        assert result == {"queued": True}

    @patch('coderabbit_ai.integrations.devin_client.requests.post')
    def test_request_401_unauthorized(self, mock_post, caplog):
        """Test request with 401 status."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        client = DevinClient(api_key="test_key")
        result = client._make_request("POST", "/test")

        assert result is None
        assert "authentication failed" in caplog.text.lower()

    @patch('coderabbit_ai.integrations.devin_client.requests.post')
    def test_request_404_not_found(self, mock_post, caplog):
        """Test request with 404 status."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_post.return_value = mock_response

        client = DevinClient(api_key="test_key")
        result = client._make_request("POST", "/test")

        assert result is None
        assert "endpoint not found" in caplog.text.lower()

    @patch('coderabbit_ai.integrations.devin_client.requests.post')
    def test_request_500_error(self, mock_post, caplog):
        """Test request with 500 status."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        client = DevinClient(api_key="test_key")
        result = client._make_request("POST", "/test")

        assert result is None
        assert "request failed" in caplog.text.lower()

    @patch('coderabbit_ai.integrations.devin_client.requests.post')
    def test_request_timeout(self, mock_post, caplog):
        """Test request timeout."""
        mock_post.side_effect = Timeout()

        client = DevinClient(api_key="test_key", timeout=10)
        result = client._make_request("POST", "/test")

        assert result is None
        assert "timed out" in caplog.text.lower()

    @patch('coderabbit_ai.integrations.devin_client.requests.post')
    def test_request_exception(self, mock_post, caplog):
        """Test request with generic exception."""
        mock_post.side_effect = Exception("Connection error")

        client = DevinClient(api_key="test_key")
        result = client._make_request("POST", "/test")

        assert result is None
        assert "request failed" in caplog.text.lower()

    def test_unsupported_method(self):
        """Test request with unsupported HTTP method."""
        client = DevinClient(api_key="test_key")
        result = client._make_request("PUT", "/test")

        assert result is None


class TestRequestIndexing:
    """Test request_indexing method."""

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_request_indexing_success(self, mock_request, caplog):
        """Test successful indexing request."""
        mock_request.return_value = {
            "request_id": "req_abc123",
            "repository": "owner/repo",
            "status": "queued",
            "estimated_time": "2-4 hours"
        }

        client = DevinClient(api_key="test_key")
        result = client.request_indexing("owner/repo")

        assert result is not None
        assert result["request_id"] == "req_abc123"
        assert result["status"] == "queued"
        mock_request.assert_called_once()

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_request_indexing_with_priority(self, mock_request):
        """Test indexing request with custom priority."""
        mock_request.return_value = {
            "request_id": "req_abc123",
            "repository": "owner/repo",
            "status": "queued"
        }

        client = DevinClient(api_key="test_key")
        result = client.request_indexing("owner/repo", priority="high")

        assert result is not None
        assert result["status"] == "queued"

    def test_request_indexing_without_api_key(self, caplog):
        """Test indexing request without API key."""
        client = DevinClient(api_key=None)
        result = client.request_indexing("owner/repo")

        assert result is None

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_request_indexing_failure(self, mock_request, caplog):
        """Test indexing request failure."""
        mock_request.return_value = None

        client = DevinClient(api_key="test_key")
        result = client.request_indexing("owner/repo")

        assert result is None
        assert "Failed to request indexing" in caplog.text


class TestCheckIndexingStatus:
    """Test check_indexing_status method."""

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_check_status_completed(self, mock_request):
        """Test checking completed indexing status."""
        mock_request.return_value = {"status": "completed"}

        client = DevinClient(api_key="test_key")
        status = client.check_indexing_status("owner/repo")

        assert status == IndexingStatus.COMPLETED

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_check_status_queued(self, mock_request):
        """Test checking queued indexing status."""
        mock_request.return_value = {"status": "queued"}

        client = DevinClient(api_key="test_key")
        status = client.check_indexing_status("owner/repo")

        assert status == IndexingStatus.QUEUED

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_check_status_in_progress(self, mock_request):
        """Test checking in_progress indexing status."""
        mock_request.return_value = {"status": "in_progress"}

        client = DevinClient(api_key="test_key")
        status = client.check_indexing_status("owner/repo")

        assert status == IndexingStatus.IN_PROGRESS

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_check_status_failed(self, mock_request):
        """Test checking failed indexing status."""
        mock_request.return_value = {"status": "failed"}

        client = DevinClient(api_key="test_key")
        status = client.check_indexing_status("owner/repo")

        assert status == IndexingStatus.FAILED

    def test_check_status_without_api_key(self):
        """Test checking status without API key."""
        client = DevinClient(api_key=None)
        status = client.check_indexing_status("owner/repo")

        assert status == IndexingStatus.UNKNOWN

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_check_status_none_response(self, mock_request):
        """Test checking status when request fails."""
        mock_request.return_value = None

        client = DevinClient(api_key="test_key")
        status = client.check_indexing_status("owner/repo")

        assert status == IndexingStatus.UNKNOWN

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_check_status_unknown_string(self, mock_request, caplog):
        """Test checking status with unknown status string."""
        mock_request.return_value = {"status": "unknown_status"}

        client = DevinClient(api_key="test_key")
        status = client.check_indexing_status("owner/repo")

        assert status == IndexingStatus.UNKNOWN
        assert "Unknown indexing status" in caplog.text


class TestGetIndexingDetails:
    """Test get_indexing_details method."""

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_get_details_success(self, mock_request):
        """Test getting indexing details successfully."""
        mock_request.return_value = {
            "request_id": "req_abc123",
            "repository": "owner/repo",
            "status": "in_progress",
            "progress_percent": 45,
            "estimated_completion": "2025-01-04T12:00:00Z"
        }

        client = DevinClient(api_key="test_key")
        result = client.get_indexing_details("owner/repo")

        assert result is not None
        assert result["progress_percent"] == 45
        assert result["status"] == "in_progress"

    def test_get_details_without_api_key(self):
        """Test getting details without API key."""
        client = DevinClient(api_key=None)
        result = client.get_indexing_details("owner/repo")

        assert result is None

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_get_details_failure(self, mock_request):
        """Test getting details when request fails."""
        mock_request.return_value = None

        client = DevinClient(api_key="test_key")
        result = client.get_indexing_details("owner/repo")

        assert result is None


class TestCancelIndexing:
    """Test cancel_indexing method."""

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_cancel_success(self, mock_request, caplog):
        """Test successful cancellation."""
        mock_request.return_value = {"status": "cancelled"}

        client = DevinClient(api_key="test_key")
        result = client.cancel_indexing("owner/repo")

        assert result == True
        assert "cancelled" in caplog.text.lower()

    def test_cancel_without_api_key(self):
        """Test cancellation without API key."""
        client = DevinClient(api_key=None)
        result = client.cancel_indexing("owner/repo")

        assert result == False

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_cancel_failure(self, mock_request, caplog):
        """Test cancellation failure."""
        mock_request.return_value = None

        client = DevinClient(api_key="test_key")
        result = client.cancel_indexing("owner/repo")

        assert result == False
        assert "Failed to cancel" in caplog.text

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_cancel_with_wrong_status(self, mock_request):
        """Test cancellation with non-cancelled status."""
        mock_request.return_value = {"status": "completed"}

        client = DevinClient(api_key="test_key")
        result = client.cancel_indexing("owner/repo")

        assert result == False


class TestListIndexedRepos:
    """Test list_indexed_repos method."""

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_list_repos_success(self, mock_request):
        """Test listing indexed repositories successfully."""
        mock_request.return_value = {
            "repositories": [
                "owner/repo1",
                "owner/repo2",
                "org/project"
            ]
        }

        client = DevinClient(api_key="test_key")
        result = client.list_indexed_repos()

        assert result is not None
        assert len(result) == 3
        assert "owner/repo1" in result

    def test_list_repos_without_api_key(self):
        """Test listing repos without API key."""
        client = DevinClient(api_key=None)
        result = client.list_indexed_repos()

        assert result is None

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_list_repos_failure(self, mock_request):
        """Test listing repos when request fails."""
        mock_request.return_value = None

        client = DevinClient(api_key="test_key")
        result = client.list_indexed_repos()

        assert result is None

    @patch('coderabbit_ai.integrations.devin_client.DevinClient._make_request')
    def test_list_repos_empty_list(self, mock_request):
        """Test listing repos with empty result."""
        mock_request.return_value = {"repositories": []}

        client = DevinClient(api_key="test_key")
        result = client.list_indexed_repos()

        assert result == []


class TestAutoRequestIfNeeded:
    """Test auto_request_if_needed method."""

    def test_auto_request_without_api_key(self):
        """Test auto request without API key."""
        client = DevinClient(api_key=None)
        result = client.auto_request_if_needed("owner/repo")

        assert result["status"] == IndexingStatus.UNKNOWN
        assert result["action"] == "none"
        assert result["needs_wait"] == False
        assert "not enabled" in result["message"]

    @patch('coderabbit_ai.integrations.devin_client.DevinClient.check_indexing_status')
    def test_already_indexed(self, mock_check):
        """Test when repository is already indexed."""
        mock_check.return_value = IndexingStatus.COMPLETED

        client = DevinClient(api_key="test_key")
        result = client.auto_request_if_needed("owner/repo")

        assert result["status"] == IndexingStatus.COMPLETED
        assert result["action"] == "already_indexed"
        assert result["needs_wait"] == False
        assert "already indexed" in result["message"]

    @patch('coderabbit_ai.integrations.devin_client.DevinClient.check_indexing_status')
    def test_status_queued(self, mock_check):
        """Test when repository is queued for indexing."""
        mock_check.return_value = IndexingStatus.QUEUED

        client = DevinClient(api_key="test_key")
        result = client.auto_request_if_needed("owner/repo")

        assert result["status"] == IndexingStatus.QUEUED
        assert result["action"] == "none"
        assert result["needs_wait"] == True
        assert "Please wait" in result["message"]

    @patch('coderabbit_ai.integrations.devin_client.DevinClient.check_indexing_status')
    def test_status_in_progress(self, mock_check):
        """Test when repository indexing is in progress."""
        mock_check.return_value = IndexingStatus.IN_PROGRESS

        client = DevinClient(api_key="test_key")
        result = client.auto_request_if_needed("owner/repo")

        assert result["status"] == IndexingStatus.IN_PROGRESS
        assert result["action"] == "none"
        assert result["needs_wait"] == True

    @patch('coderabbit_ai.integrations.devin_client.DevinClient.check_indexing_status')
    @patch('coderabbit_ai.integrations.devin_client.DevinClient.request_indexing')
    def test_auto_request_success(self, mock_request, mock_check):
        """Test successful auto request."""
        mock_check.return_value = IndexingStatus.NOT_STARTED
        mock_request.return_value = {
            "request_id": "req_abc123",
            "status": "queued"
        }

        client = DevinClient(api_key="test_key")
        result = client.auto_request_if_needed("owner/repo", auto_request=True)

        assert result["status"] == IndexingStatus.QUEUED
        assert result["action"] == "requested"
        assert result["needs_wait"] == True
        assert "Indexing requested" in result["message"]
        assert "req_abc123" in result["message"]

    @patch('coderabbit_ai.integrations.devin_client.DevinClient.check_indexing_status')
    @patch('coderabbit_ai.integrations.devin_client.DevinClient.request_indexing')
    def test_auto_request_failure(self, mock_request, mock_check):
        """Test failed auto request."""
        mock_check.return_value = IndexingStatus.FAILED
        mock_request.return_value = None

        client = DevinClient(api_key="test_key")
        result = client.auto_request_if_needed("owner/repo", auto_request=True)

        assert result["action"] == "failed"
        assert result["needs_wait"] == False
        assert "Failed to request" in result["message"]

    @patch('coderabbit_ai.integrations.devin_client.DevinClient.check_indexing_status')
    def test_no_auto_request(self, mock_check):
        """Test without auto_request flag."""
        mock_check.return_value = IndexingStatus.NOT_STARTED

        client = DevinClient(api_key="test_key")
        result = client.auto_request_if_needed("owner/repo", auto_request=False)

        assert result["action"] == "none"
        assert result["needs_wait"] == False
        assert "Call request_indexing" in result["message"]

    @patch('coderabbit_ai.integrations.devin_client.DevinClient.check_indexing_status')
    def test_unknown_status(self, mock_check):
        """Test with unknown status."""
        mock_check.return_value = IndexingStatus.UNKNOWN

        client = DevinClient(api_key="test_key")
        result = client.auto_request_if_needed("owner/repo", auto_request=True)

        assert result["action"] == "none"
        assert result["needs_wait"] == False
