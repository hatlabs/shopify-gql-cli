"""Customer queries."""

from shopify_gql_cli.core.client import ShopifyClient

LIST_CUSTOMERS_QUERY = """
query($first: Int!, $after: String, $query: String) {
  customers(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        displayName
        email
        phone
        state
        numberOfOrders
        amountSpent { amount currencyCode }
        createdAt
        defaultAddress {
          address1
          city
          country
          zip
        }
      }
      cursor
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

GET_CUSTOMER_QUERY = """
query($id: ID!) {
  customer(id: $id) {
    id
    displayName
    firstName
    lastName
    email
    phone
    state
    note
    tags
    numberOfOrders
    amountSpent { amount currencyCode }
    createdAt
    updatedAt
    defaultAddress {
      address1
      address2
      city
      province
      country
      zip
      phone
    }
    addresses {
      address1
      city
      country
      zip
    }
    orders(first: 10) {
      edges {
        node {
          id
          name
          createdAt
          displayFinancialStatus
          totalPriceSet { shopMoney { amount currencyCode } }
        }
      }
    }
  }
}
"""


def _ensure_gid(raw_id: str, resource: str = "Customer") -> str:
    if raw_id.startswith("gid://"):
        return raw_id
    return f"gid://shopify/{resource}/{raw_id}"


def list_customers(
    client: ShopifyClient,
    first: int = 10,
    after: str | None = None,
    query: str | None = None,
) -> dict:
    """Query customers with optional search string."""
    result = client.execute(
        LIST_CUSTOMERS_QUERY, {"first": first, "after": after, "query": query}
    )
    return result["data"]["customers"]


def get_customer(client: ShopifyClient, customer_id: str) -> dict:
    """Get a single customer by ID."""
    gid = _ensure_gid(customer_id, "Customer")
    result = client.execute(GET_CUSTOMER_QUERY, {"id": gid})
    return result["data"]["customer"]
