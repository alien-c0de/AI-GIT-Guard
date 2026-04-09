"""
tests/test_client.py — Unit tests for github/client.py (GitHubClient).
Tests rate-limit retry, pagination, error handling, and token validation.
"""

import time
import pytest
import httpx
from unittest.mock import patch, MagicMock
from github.client import (
    GitHubClient, GitHubAPIError, RateLimitExceeded, GitHubNetworkError,
)


class TestRateLimitRetry:
    """Verify that rate-limited responses are retried instead of just raising."""

    def test_sleep_for_rate_limit_calculates_wait(self):
        client = GitHubClient.__new__(GitHubClient)
        mock_response = MagicMock()
        mock_response.headers = {"X-RateLimit-Reset": str(int(time.time()) + 10)}
        mock_response.status_code = 429

        with patch("time.sleep") as mock_sleep:
            client._sleep_for_rate_limit(mock_response)
            mock_sleep.assert_called_once()
            wait_arg = mock_sleep.call_args[0][0]
            assert 5 <= wait_arg <= 15

    def test_request_retries_on_rate_limit(self):
        """_request should retry after sleeping when rate-limited."""
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()

        # First call returns 429, second returns 200
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"X-RateLimit-Reset": str(int(time.time()) + 1)}
        resp_429.url = "https://api.github.com/test"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.is_success = True
        resp_200.url = "https://api.github.com/test"

        client._client.get = MagicMock(side_effect=[resp_429, resp_200])

        with patch("time.sleep"):
            result = client._request("/test")
            assert result == resp_200
            assert client._client.get.call_count == 2

    def test_request_raises_after_max_retries(self):
        """After MAX_RATE_LIMIT_RETRIES, should raise RateLimitExceeded."""
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()

        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"X-RateLimit-Reset": str(int(time.time()) + 1)}
        resp_429.url = "https://api.github.com/test"

        # All calls return 429
        client._client.get = MagicMock(return_value=resp_429)

        with patch("time.sleep"):
            with pytest.raises(RateLimitExceeded, match="Rate limit exceeded"):
                client._request("/test")


class TestErrorHandling:
    """Test that network errors are wrapped properly."""

    def test_connect_error_raises_network_error(self):
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()
        client._client.get = MagicMock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(GitHubNetworkError, match="Cannot reach GitHub API"):
            client._request("/test")

    def test_timeout_raises_network_error(self):
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()
        client._client.get = MagicMock(side_effect=httpx.ReadTimeout("timeout"))

        with pytest.raises(GitHubNetworkError, match="timed out"):
            client._request("/test")

    def test_404_raises_api_error(self):
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()

        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.url = "https://api.github.com/test"
        client._client.get = MagicMock(return_value=resp_404)

        with pytest.raises(GitHubAPIError, match="Not found"):
            client._request("/test")


class TestPagination:
    """Test that paginate() follows pages correctly."""

    def test_single_page(self):
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()

        items = [{"id": i} for i in range(5)]
        resp = MagicMock()
        resp.status_code = 200
        resp.is_success = True
        resp.url = "https://api.github.com/test"
        resp.json = MagicMock(return_value=items)
        resp.headers = {}
        client._client.get = MagicMock(return_value=resp)

        result = list(client.paginate("/test"))
        assert len(result) == 5

    def test_empty_response(self):
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()

        resp = MagicMock()
        resp.status_code = 200
        resp.is_success = True
        resp.url = "https://api.github.com/test"
        resp.json = MagicMock(return_value=[])
        resp.headers = {}
        client._client.get = MagicMock(return_value=resp)

        result = list(client.paginate("/test"))
        assert result == []


class TestTokenValidation:
    """Test validate_token with scope checking."""

    def test_valid_token_returns_true(self):
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()

        resp = MagicMock()
        resp.status_code = 200
        resp.is_success = True
        resp.url = "https://api.github.com/user"
        resp.json = MagicMock(return_value={"login": "test"})
        resp.headers = {"X-OAuth-Scopes": "security_events, read:org, repo"}
        client._client.get = MagicMock(return_value=resp)

        assert client.validate_token() is True

    def test_invalid_token_returns_false(self):
        client = GitHubClient.__new__(GitHubClient)
        client._base_url = "https://api.github.com"
        client._client = MagicMock()

        resp = MagicMock()
        resp.status_code = 401
        resp.is_success = False
        resp.url = "https://api.github.com/user"
        resp.text = "Bad credentials"
        resp.json = MagicMock(return_value={"message": "Bad credentials"})
        resp.headers = {}
        client._client.get = MagicMock(return_value=resp)

        assert client.validate_token() is False
