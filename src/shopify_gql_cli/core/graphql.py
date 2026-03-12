"""Raw GraphQL query execution."""

import json

from shopify_gql_cli.core.client import ShopifyClient


def execute_raw(
    client: ShopifyClient, query: str, variables: dict | None = None
) -> dict:
    """Execute an arbitrary GraphQL query/mutation and return the full response."""
    return client.execute(query, variables)


def parse_variables(variables_json: str | None) -> dict | None:
    """Parse a JSON string into a variables dict, or return None."""
    if not variables_json:
        return None
    return json.loads(variables_json)
