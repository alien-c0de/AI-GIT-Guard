"""
github/client.py — Low-level GitHub REST API client.
Handles authentication, pagination, rate-limit back-off, and
GitHub Enterprise base-URL switching.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Generator, Optional
from urllib.parse import urljoin

import httpx

from config import settings

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Raised when the GitHub API returns an error response."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"GitHub API error {status_code}: {message}")


class RateLimitExceeded(GitHubAPIError):
    """Raised when the 403/429 rate-limit is hit."""
    pass


class GitHubNetworkError(Exception):
    """
    Raised when a network-level failure prevents reaching the GitHub API.
    Common causes: corporate firewall, missing proxy, no internet access.
    """
    pass


class GitHubClient:
    """
    Thin httpx wrapper around the GitHub REST API v3.
    Supports both github.com and GitHub Enterprise Server.
    """

    DEFAULT_BASE = "https://api.github.com"
    PAGE_SIZE = 100  # Maximum allowed by GitHub

    def __init__(self) -> None:
        base = settings.GITHUB_ENTERPRISE_URL
        if base:
            # GHE: API lives at <base>/api/v3/
            self._base_url = base.rstrip("/") + "/api/v3"
        else:
            self._base_url = self.DEFAULT_BASE

        self._headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            timeout=30.0,
        )
        logger.debug("GitHubClient initialised — base: %s", self._base_url)

    MAX_RATE_LIMIT_RETRIES = 2

    # ── Core request helpers ─────────────────────────────────────────────────

    def _request(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        """Make a single GET request with rate-limit retry; raises on error."""
        for attempt in range(self.MAX_RATE_LIMIT_RETRIES + 1):
            logger.debug("GET %s params=%s (attempt %d)", path, params, attempt + 1)
            try:
                response = self._client.get(path, params=params)
            except httpx.ProxyError as exc:
                raise GitHubNetworkError(
                    "Connection failed: a proxy error was encountered.\n"
                    "Check your HTTP_PROXY / HTTPS_PROXY environment variables."
                ) from exc
            except httpx.ConnectError as exc:
                raise GitHubNetworkError(
                    f"Cannot reach GitHub API ({self._base_url}).\n"
                    "The connection was actively refused — your corporate firewall or proxy "
                    "may be blocking outbound HTTPS traffic to api.github.com.\n"
                    "Try: set HTTPS_PROXY in your .env or check with your network team."
                ) from exc
            except httpx.TimeoutException as exc:
                raise GitHubNetworkError(
                    f"Request timed out connecting to {self._base_url}.\n"
                    "The server took too long to respond. Check network latency or increase timeout."
                ) from exc
            except httpx.NetworkError as exc:
                raise GitHubNetworkError(
                    f"A network error occurred while contacting {self._base_url}: {exc}"
                ) from exc
            logger.debug("Response %d from %s", response.status_code, response.url)

            # Handle rate limiting with retry
            if response.status_code in (403, 429):
                if attempt < self.MAX_RATE_LIMIT_RETRIES:
                    self._sleep_for_rate_limit(response)
                    continue  # retry the request
                raise RateLimitExceeded(response.status_code, "Rate limit exceeded after retries")

            if response.status_code == 404:
                raise GitHubAPIError(404, f"Not found: {path}")
            if not response.is_success:
                try:
                    body = response.json()
                    msg = body.get("message", response.text) if isinstance(body, dict) else response.text
                except Exception:
                    msg = response.text
                raise GitHubAPIError(response.status_code, msg)
            return response

        # Should not be reached, but satisfy type checker
        raise RateLimitExceeded(429, "Rate limit exceeded after retries")

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        """Make a single GET request; raises on error; returns parsed JSON."""
        return self._request(path, params).json()

    def _sleep_for_rate_limit(self, response: httpx.Response) -> None:
        """Sleep until the rate-limit window resets."""
        reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
        wait = max(reset_ts - int(time.time()), 5)
        logger.warning("Rate limit hit — sleeping %d seconds before retry…", wait)
        time.sleep(wait)

    def paginate(self, path: str, params: Optional[dict] = None) -> Generator[dict, None, None]:
        """
        Yield all items across paginated GitHub list endpoints.
        Automatically follows Link: <next> headers until exhausted.
        Works with both page-based and cursor-based pagination.
        """
        params = dict(params or {})
        params.setdefault("per_page", self.PAGE_SIZE)

        current_path = path
        current_params: Optional[dict] = params

        while True:
            response = self._request(current_path, current_params)
            data = response.json()

            if not data:
                break

            if isinstance(data, list):
                yield from data
                if len(data) < self.PAGE_SIZE:
                    break
            else:
                items = data.get("items") or data.get("alerts") or []
                yield from items
                if len(items) < self.PAGE_SIZE:
                    break

            # Follow Link: <url>; rel="next" header for next page
            next_url = self._parse_next_link(response)
            if not next_url:
                break
            # The next URL is absolute — pass it directly, no extra params
            current_path = next_url
            current_params = None

    @staticmethod
    def _parse_next_link(response: httpx.Response) -> Optional[str]:
        """Extract the 'next' URL from the Link response header, if present."""
        link_header = response.headers.get("Link", "")
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                # Extract URL between < and >
                url = part.split(";")[0].strip().strip("<>")
                return url
        return None

    # ── Organisation helpers ─────────────────────────────────────────────────

    def list_user_orgs(self) -> list[dict]:
        """Return all organisations the authenticated user belongs to."""
        logger.info("Fetching organisations for authenticated user")
        return list(self.paginate("/user/orgs"))

    # ── Repository helpers ───────────────────────────────────────────────────

    def list_repos(self, org: str) -> list[dict]:
        """Return all repositories for the given organisation."""
        logger.info("Fetching repos for org: %s", org)
        return list(self.paginate(f"/orgs/{org}/repos", {"type": "all"}))

    def get_repo_details(self, owner: str, repo: str) -> dict:
        """Return full repository metadata (language, visibility, size, etc.)."""
        return self._get(f"/repos/{owner}/{repo}")

    # ── Dependabot ───────────────────────────────────────────────────────────

    def get_org_dependabot_alerts(self, org: str, state: str = "open") -> list[dict]:
        logger.info("Fetching Dependabot alerts for org: %s (state=%s)", org, state)
        return list(self.paginate(f"/orgs/{org}/dependabot/alerts", {"state": state}))

    def get_repo_dependabot_alerts(self, owner: str, repo: str, state: str = "open") -> list[dict]:
        logger.info("Fetching Dependabot alerts for %s/%s", owner, repo)
        return list(self.paginate(f"/repos/{owner}/{repo}/dependabot/alerts", {"state": state}))

    # ── Code Scanning ────────────────────────────────────────────────────────

    def get_org_code_scanning_alerts(self, org: str, state: str = "open") -> list[dict]:
        logger.info("Fetching Code Scanning alerts for org: %s", org)
        return list(self.paginate(f"/orgs/{org}/code-scanning/alerts", {"state": state}))

    def get_repo_code_scanning_alerts(self, owner: str, repo: str, state: str = "open") -> list[dict]:
        logger.info("Fetching Code Scanning alerts for %s/%s", owner, repo)
        return list(self.paginate(f"/repos/{owner}/{repo}/code-scanning/alerts", {"state": state}))

    # ── Secret Scanning ──────────────────────────────────────────────────────

    def get_org_secret_scanning_alerts(self, org: str, state: str = "open") -> list[dict]:
        logger.info("Fetching Secret Scanning alerts for org: %s", org)
        return list(self.paginate(f"/orgs/{org}/secret-scanning/alerts", {"state": state}))

    def get_repo_secret_scanning_alerts(self, owner: str, repo: str, state: str = "open") -> list[dict]:
        logger.info("Fetching Secret Scanning alerts for %s/%s", owner, repo)
        return list(self.paginate(f"/repos/{owner}/{repo}/secret-scanning/alerts", {"state": state}))

    # ── GitHub Actions Workflows ────────────────────────────────────────────

    def list_repo_workflows(self, owner: str, repo: str) -> list[dict]:
        """List workflow files from .github/workflows/ via the Contents API."""
        logger.info("Listing workflow files for %s/%s", owner, repo)
        try:
            data = self._get(f"/repos/{owner}/{repo}/contents/.github/workflows")
            if isinstance(data, list):
                return [f for f in data if f.get("name", "").endswith((".yml", ".yaml"))]
            return []
        except GitHubAPIError as exc:
            if exc.status_code == 404:
                return []  # No workflows directory
            raise

    def get_file_content(self, owner: str, repo: str, path: str) -> str | None:
        """Fetch the decoded text content of a file via the Contents API."""
        import base64 as _b64
        logger.info("Fetching file content: %s/%s/%s", owner, repo, path)
        try:
            data = self._get(f"/repos/{owner}/{repo}/contents/{path}")
            if isinstance(data, dict) and data.get("encoding") == "base64":
                return _b64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return data.get("content", "") if isinstance(data, dict) else None
        except GitHubAPIError as exc:
            if exc.status_code == 404:
                return None
            raise

    def validate_token(self) -> bool:
        """Quick connectivity + token check. Also warns if required scopes are missing."""
        try:
            response = self._request("/user")
            # Check token scopes for fine-grained permissions
            scopes = response.headers.get("X-OAuth-Scopes", "")
            if scopes:
                granted = {s.strip() for s in scopes.split(",")}
                required = {"security_events", "read:org"}
                missing = required - granted
                if missing:
                    logger.warning(
                        "GitHub token may be missing scopes: %s. "
                        "Some API endpoints may return 404.",
                        ", ".join(sorted(missing)),
                    )
            return True
        except GitHubAPIError as exc:
            logger.error("Token validation failed: %s", exc)
            return False

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
