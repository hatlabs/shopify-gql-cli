"""Shop info queries."""

from shopify_gql_cli.core.client import ShopifyClient

SHOP_INFO_QUERY = """
query {
  shop {
    name
    email
    myshopifyDomain
    primaryDomain { host url }
    plan { displayName shopifyPlus }
    currencyCode
    billingAddress {
      address1
      city
      country
      zip
    }
    timezoneAbbreviation
  }
}
"""

LOCATIONS_QUERY = """
query($first: Int!, $after: String) {
  locations(first: $first, after: $after) {
    edges {
      node {
        id
        name
        isActive
        address { address1 city country zip }
      }
      cursor
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def get_shop_info(client: ShopifyClient) -> dict:
    """Return basic shop information."""
    result = client.execute(SHOP_INFO_QUERY)
    return result["data"]["shop"]


def get_locations(client: ShopifyClient, first: int = 10, after: str | None = None) -> dict:
    """Return shop locations."""
    result = client.execute(LOCATIONS_QUERY, {"first": first, "after": after})
    return result["data"]["locations"]
