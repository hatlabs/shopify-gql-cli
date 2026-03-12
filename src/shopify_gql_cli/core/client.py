"""Shopify Admin GraphQL API client."""

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class ShopifyAPIError(Exception):
    """Raised when the Shopify API returns an error."""

    def __init__(self, message: str, status_code: int | None = None, errors: list | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or []


class ShopifyRateLimitError(ShopifyAPIError):
    """Raised when Shopify rate limit is hit."""

    def __init__(self, retry_after: float = 1.0):
        super().__init__(f"Rate limited. Retry after {retry_after}s", status_code=429)
        self.retry_after = retry_after


@dataclass
class ShopifyClient:
    """HTTP client for Shopify Admin GraphQL API."""

    store: str
    token: str
    api_version: str = "2026-01"

    @property
    def endpoint(self) -> str:
        return f"https://{self.store}/admin/api/{self.api_version}/graphql.json"

    def execute(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query/mutation and return the parsed response.

        Handles rate limiting with automatic retry (once).
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.token,
        }

        for attempt in range(2):
            req = urllib.request.Request(
                self.endpoint, data=body, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    retry_after = float(e.headers.get("Retry-After", "2.0"))
                    if attempt == 0:
                        time.sleep(retry_after)
                        continue
                    raise ShopifyRateLimitError(retry_after) from e
                if e.code == 401:
                    raise ShopifyAPIError(
                        "Authentication failed. Check SHOPIFY_ACCESS_TOKEN.",
                        status_code=401,
                    ) from e
                error_body = e.read().decode("utf-8", errors="replace")
                raise ShopifyAPIError(
                    f"HTTP {e.code}: {error_body}", status_code=e.code
                ) from e
            except urllib.error.URLError as e:
                raise ShopifyAPIError(f"Connection error: {e.reason}") from e

            if "errors" in data and not data.get("data"):
                raise ShopifyAPIError(
                    "; ".join(e.get("message", str(e)) for e in data["errors"]),
                    errors=data["errors"],
                )

            return data

        raise ShopifyAPIError("Request failed after retry")


def make_client(store: str | None = None, token: str | None = None) -> ShopifyClient:
    """Create a ShopifyClient from explicit args or environment variables."""
    store = store or os.environ.get("SHOPIFY_STORE_URL")
    token = token or os.environ.get("SHOPIFY_ACCESS_TOKEN")

    if not store:
        raise ShopifyAPIError(
            "SHOPIFY_STORE_URL not set. Provide --store or set the env var."
        )
    if not token:
        raise ShopifyAPIError(
            "SHOPIFY_ACCESS_TOKEN not set. Provide --token or set the env var."
        )

    return ShopifyClient(store=store, token=token)
