"""E2E tests for shopify-gql-cli.

Requires live Shopify API access:
  SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN must be set.
"""

import json
import os
import subprocess
import sys

import pytest

from shopify_gql_cli.core.client import ShopifyClient, make_client
from shopify_gql_cli.core import customers, graphql, orders, products, shop


def _has_shopify_credentials() -> bool:
    return bool(
        os.environ.get("SHOPIFY_STORE_URL") and os.environ.get("SHOPIFY_ACCESS_TOKEN")
    )


requires_shopify = pytest.mark.skipif(
    not _has_shopify_credentials(),
    reason="SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN not set",
)


@pytest.fixture
def client():
    return make_client()


def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil

    force = os.environ.get("SHOPIFY_GQL_CLI_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "shopify_gql_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ---------------------------------------------------------------------------
# API-level E2E tests
# ---------------------------------------------------------------------------


@requires_shopify
class TestShopE2E:
    def test_shop_info(self, client):
        result = shop.get_shop_info(client)
        assert "name" in result
        assert "currencyCode" in result
        print(f"\n  Shop: {result['name']} ({result['currencyCode']})")

    def test_shop_info_has_domain(self, client):
        result = shop.get_shop_info(client)
        assert "myshopifyDomain" in result
        assert ".myshopify.com" in result["myshopifyDomain"]


@requires_shopify
class TestOrdersE2E:
    def test_list_orders(self, client):
        result = orders.list_orders(client, first=3)
        assert "edges" in result
        for edge in result["edges"]:
            node = edge["node"]
            assert "id" in node
            assert "name" in node
        print(f"\n  Fetched {len(result['edges'])} orders")

    def test_list_orders_with_query(self, client):
        result = orders.list_orders(client, first=5, query="financial_status:paid")
        assert "edges" in result


@requires_shopify
class TestProductsE2E:
    def test_list_products(self, client):
        result = products.list_products(client, first=3)
        assert "edges" in result
        for edge in result["edges"]:
            node = edge["node"]
            assert "id" in node
            assert "title" in node
        print(f"\n  Fetched {len(result['edges'])} products")

    def test_get_product(self, client):
        listing = products.list_products(client, first=1)
        if listing["edges"]:
            product_id = listing["edges"][0]["node"]["id"]
            result = products.get_product(client, product_id)
            assert result["id"] == product_id
            assert "title" in result
            print(f"\n  Product: {result['title']}")


@requires_shopify
class TestCustomersE2E:
    def test_list_customers(self, client):
        result = customers.list_customers(client, first=2)
        assert "edges" in result
        print(f"\n  Fetched {len(result['edges'])} customers")


@requires_shopify
class TestGraphqlE2E:
    def test_raw_query(self, client):
        result = graphql.execute_raw(client, "{ shop { name } }")
        assert result["data"]["shop"]["name"]


# ---------------------------------------------------------------------------
# CLI subprocess tests
# ---------------------------------------------------------------------------


@requires_shopify
class TestCLISubprocess:
    CLI_BASE = _resolve_cli("shopify-gql-cli")

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Shopify" in result.stdout

    def test_shop_info_json(self):
        result = self._run(["--json", "shop", "info"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "name" in data
        print(f"\n  Shop (subprocess): {data['name']}")

    def test_orders_list_json(self):
        result = self._run(["--json", "orders", "list", "--first", "2"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "nodes" in data
        print(f"\n  Orders (subprocess): {len(data['nodes'])} fetched")

    def test_products_list_json(self):
        result = self._run(["--json", "products", "list", "--first", "2"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "nodes" in data
        print(f"\n  Products (subprocess): {len(data['nodes'])} fetched")

    def test_graphql_execute_json(self):
        result = self._run(["--json", "graphql", "execute", "{ shop { name } }"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "data" in data
        assert data["data"]["shop"]["name"]
