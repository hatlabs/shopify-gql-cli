"""Unit tests for shopify-gql-cli core modules."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from shopify_gql_cli.core.client import (
    ShopifyAPIError,
    ShopifyClient,
    make_client,
)
from shopify_gql_cli.core.graphql import execute_raw, parse_variables
from shopify_gql_cli.core.orders import _has_filter


# ---------------------------------------------------------------------------
# client.py tests
# ---------------------------------------------------------------------------


class TestMakeClient:
    def test_from_explicit_args(self):
        client = make_client(store="test.myshopify.com", token="shpat_xxx")
        assert client.store == "test.myshopify.com"
        assert client.token == "shpat_xxx"

    def test_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("SHOPIFY_STORE_URL", "env.myshopify.com")
        monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_env")
        client = make_client()
        assert client.store == "env.myshopify.com"
        assert client.token == "shpat_env"

    def test_missing_store_raises(self, monkeypatch):
        monkeypatch.delenv("SHOPIFY_STORE_URL", raising=False)
        monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
        with pytest.raises(ShopifyAPIError, match="SHOPIFY_STORE_URL"):
            make_client(token="shpat_xxx")

    def test_missing_token_raises(self, monkeypatch):
        monkeypatch.delenv("SHOPIFY_STORE_URL", raising=False)
        monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
        with pytest.raises(ShopifyAPIError, match="SHOPIFY_ACCESS_TOKEN"):
            make_client(store="test.myshopify.com")

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv("SHOPIFY_STORE_URL", "env.myshopify.com")
        monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_env")
        client = make_client(store="explicit.myshopify.com", token="shpat_explicit")
        assert client.store == "explicit.myshopify.com"
        assert client.token == "shpat_explicit"


class TestShopifyClient:
    def test_endpoint_url(self):
        client = ShopifyClient(store="test.myshopify.com", token="shpat_xxx")
        assert client.endpoint == "https://test.myshopify.com/admin/api/2026-01/graphql.json"

    def test_custom_api_version(self):
        client = ShopifyClient(
            store="test.myshopify.com", token="shpat_xxx", api_version="2025-10"
        )
        assert "2025-10" in client.endpoint


# ---------------------------------------------------------------------------
# graphql.py tests
# ---------------------------------------------------------------------------


class TestParseVariables:
    def test_valid_json(self):
        result = parse_variables('{"id": "gid://shopify/Product/123"}')
        assert result == {"id": "gid://shopify/Product/123"}

    def test_none_input(self):
        assert parse_variables(None) is None

    def test_empty_string(self):
        assert parse_variables("") is None

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_variables("not json")

    def test_complex_variables(self):
        result = parse_variables('{"first": 10, "query": "status:active"}')
        assert result["first"] == 10
        assert result["query"] == "status:active"


# ---------------------------------------------------------------------------
# orders.py tests
# ---------------------------------------------------------------------------


class TestHasFilter:
    def test_at_start(self):
        assert _has_filter("status:open", "status") is True

    def test_after_space(self):
        assert _has_filter("name:123 status:any", "status") is True

    def test_absent(self):
        assert _has_filter("financial_status:paid", "status") is False

    def test_name_filter(self):
        assert _has_filter("name:#A2488", "name") is True


class TestListOrdersQuery:
    """Verify the effective query string built by list_orders."""

    def _capture(self, query: str | None) -> str:
        from unittest.mock import MagicMock
        from shopify_gql_cli.core.orders import list_orders

        client = MagicMock()
        client.execute.return_value = {
            "data": {"orders": {"edges": [], "pageInfo": {}}}
        }
        list_orders(client, query=query)
        variables = client.execute.call_args[0][1]
        return variables["query"]

    def test_no_query_defaults_open(self):
        assert self._capture(None) == "status:open"

    def test_plain_query_prepends_open(self):
        assert self._capture("financial_status:paid") == "status:open financial_status:paid"

    def test_explicit_status_preserved(self):
        assert self._capture("status:any") == "status:any"

    def test_explicit_status_mid_query(self):
        assert self._capture("financial_status:paid status:closed") == "financial_status:paid status:closed"

    def test_name_query_uses_status_any(self):
        assert self._capture("name:#A2488") == "status:any name:#A2488"

    def test_name_query_with_explicit_status(self):
        assert self._capture("status:open name:#A2488") == "status:open name:#A2488"
