"""Order queries and mutations."""

from shopify_gql_cli.core.client import ShopifyClient

LIST_ORDERS_QUERY = """
query($first: Int!, $after: String, $query: String) {
  orders(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        name
        createdAt
        displayFinancialStatus
        displayFulfillmentStatus
        totalPriceSet { shopMoney { amount currencyCode } }
        customer { displayName email }
        lineItems(first: 5) {
          edges {
            node {
              title
              quantity
              originalUnitPriceSet { shopMoney { amount currencyCode } }
            }
          }
        }
      }
      cursor
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

GET_ORDER_QUERY = """
query($id: ID!) {
  order(id: $id) {
    id
    name
    createdAt
    closedAt
    cancelledAt
    displayFinancialStatus
    displayFulfillmentStatus
    note
    tags
    totalPriceSet { shopMoney { amount currencyCode } }
    subtotalPriceSet { shopMoney { amount currencyCode } }
    totalTaxSet { shopMoney { amount currencyCode } }
    totalShippingPriceSet { shopMoney { amount currencyCode } }
    customer { id displayName email phone }
    shippingAddress {
      address1
      address2
      city
      country
      zip
    }
    lineItems(first: 50) {
      edges {
        node {
          id
          title
          sku
          quantity
          originalUnitPriceSet { shopMoney { amount currencyCode } }
          variant { id title }
        }
      }
    }
    fulfillments {
      id
      status
      trackingInfo { number url company }
    }
  }
}
"""

CANCEL_ORDER_MUTATION = """
mutation($orderId: ID!, $reason: OrderCancelReason, $notifyCustomer: Boolean, $refund: Boolean, $restock: Boolean, $staffNote: String) {
  orderCancel(
    orderId: $orderId
    reason: $reason
    notifyCustomer: $notifyCustomer
    refund: $refund
    restock: $restock
    staffNote: $staffNote
  ) {
    job { id }
    orderCancelUserErrors { field message code }
  }
}
"""

CLOSE_ORDER_MUTATION = """
mutation($input: OrderCloseInput!) {
  orderClose(input: $input) {
    order { id name }
    userErrors { field message }
  }
}
"""


def _ensure_gid(raw_id: str, resource: str = "Order") -> str:
    """Convert a plain numeric ID to a Shopify GID if needed."""
    if raw_id.startswith("gid://"):
        return raw_id
    return f"gid://shopify/{resource}/{raw_id}"


def _has_filter(query: str, key: str) -> bool:
    """Check whether *query* already contains a ``key:`` filter."""
    return query.startswith(f"{key}:") or f" {key}:" in query


def list_orders(
    client: ShopifyClient,
    first: int = 10,
    after: str | None = None,
    query: str | None = None,
) -> dict:
    """Query orders with optional search string.

    Defaults to open orders only unless the query targets a specific order
    (e.g. ``name:``), in which case ``status:any`` is used so that
    closed / fulfilled orders are not silently excluded.  Pass an explicit
    ``status:`` filter to override in either case.
    """
    if not query:
        effective_query = "status:open"
    elif _has_filter(query, "status"):
        effective_query = query
    elif _has_filter(query, "name"):
        effective_query = f"status:any {query}"
    else:
        effective_query = f"status:open {query}"
    result = client.execute(
        LIST_ORDERS_QUERY, {"first": first, "after": after, "query": effective_query}
    )
    return result["data"]["orders"]


def get_order(client: ShopifyClient, order_id: str) -> dict:
    """Get a single order by ID (accepts plain numeric or full GID)."""
    gid = _ensure_gid(order_id, "Order")
    result = client.execute(GET_ORDER_QUERY, {"id": gid})
    return result["data"]["order"]


def cancel_order(
    client: ShopifyClient,
    order_id: str,
    reason: str | None = None,
    notify_customer: bool = False,
    refund: bool = True,
    restock: bool = True,
    staff_note: str | None = None,
) -> dict:
    """Cancel an order."""
    gid = _ensure_gid(order_id, "Order")
    variables: dict = {
        "orderId": gid,
        "notifyCustomer": notify_customer,
        "refund": refund,
        "restock": restock,
    }
    if reason:
        variables["reason"] = reason
    if staff_note:
        variables["staffNote"] = staff_note
    result = client.execute(CANCEL_ORDER_MUTATION, variables)
    return result["data"]["orderCancel"]


def close_order(client: ShopifyClient, order_id: str) -> dict:
    """Close an order."""
    gid = _ensure_gid(order_id, "Order")
    result = client.execute(CLOSE_ORDER_MUTATION, {"input": {"id": gid}})
    return result["data"]["orderClose"]
