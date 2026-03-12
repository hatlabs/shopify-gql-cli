"""Backend utilities for Shopify GraphQL API access."""

from shopify_gql_cli.core.client import ShopifyClient, make_client


def get_client(store: str | None = None, token: str | None = None) -> ShopifyClient:
    """Create and return a configured ShopifyClient."""
    return make_client(store=store, token=token)


def execute_graphql(
    query: str,
    variables: dict | None = None,
    store: str | None = None,
    token: str | None = None,
) -> dict:
    """Low-level helper: create a client and execute a query in one call."""
    client = get_client(store=store, token=token)
    return client.execute(query, variables)
