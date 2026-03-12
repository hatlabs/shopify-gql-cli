"""Inventory queries and mutations."""

from shopify_gql_cli.core.client import ShopifyAPIError, ShopifyClient

INVENTORY_LEVELS_QUERY = """
query($first: Int!, $after: String, $query: String) {
  inventoryItems(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        sku
        tracked
        inventoryLevels(first: 10) {
          edges {
            node {
              id
              quantities(names: ["available", "on_hand", "committed", "reserved"]) {
                name
                quantity
              }
              location { id name }
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

INVENTORY_ITEM_LEVELS_QUERY = """
query($id: ID!) {
  inventoryItem(id: $id) {
    id
    sku
    tracked
    inventoryLevels(first: 20) {
      edges {
        node {
          id
          quantities(names: ["available", "on_hand", "committed", "reserved"]) {
            name
            quantity
          }
          location { id name }
        }
      }
    }
  }
}
"""

ADJUST_QUANTITIES_MUTATION = """
mutation($input: InventoryAdjustQuantitiesInput!) {
  inventoryAdjustQuantities(input: $input) {
    inventoryAdjustmentGroup {
      reason
      changes {
        name
        delta
        item { id sku }
        location { id name }
      }
    }
    userErrors { field message code }
  }
}
"""

SET_QUANTITIES_MUTATION = """
mutation($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) {
    inventoryAdjustmentGroup {
      reason
      changes {
        name
        delta
        item { id sku }
        location { id name }
      }
    }
    userErrors { field message code }
  }
}
"""


def _ensure_gid(raw_id: str, resource: str) -> str:
    if raw_id.startswith("gid://"):
        return raw_id
    return f"gid://shopify/{resource}/{raw_id}"


def get_inventory_levels(
    client: ShopifyClient,
    first: int = 10,
    after: str | None = None,
    query: str | None = None,
) -> dict:
    """Get inventory levels for items, optionally filtered by query string."""
    result = client.execute(
        INVENTORY_LEVELS_QUERY, {"first": first, "after": after, "query": query}
    )
    return result["data"]["inventoryItems"]


def get_inventory_item_levels(client: ShopifyClient, inventory_item_id: str) -> dict:
    """Get inventory levels for a specific inventory item."""
    gid = _ensure_gid(inventory_item_id, "InventoryItem")
    result = client.execute(INVENTORY_ITEM_LEVELS_QUERY, {"id": gid})
    return result["data"]["inventoryItem"]


def adjust_inventory(
    client: ShopifyClient,
    inventory_item_id: str,
    location_id: str,
    delta: int,
    reason: str = "correction",
    name: str = "available",
) -> dict:
    """Adjust inventory quantity by a delta amount."""
    item_gid = _ensure_gid(inventory_item_id, "InventoryItem")
    loc_gid = _ensure_gid(location_id, "Location")

    input_data = {
        "reason": reason,
        "name": name,
        "changes": [
            {
                "delta": delta,
                "inventoryItemId": item_gid,
                "locationId": loc_gid,
            }
        ],
    }

    result = client.execute(ADJUST_QUANTITIES_MUTATION, {"input": input_data})
    payload = result["data"]["inventoryAdjustQuantities"]
    if payload["userErrors"]:
        errors = "; ".join(e["message"] for e in payload["userErrors"])
        raise ShopifyAPIError(f"Inventory adjust failed: {errors}")
    return payload


def set_inventory(
    client: ShopifyClient,
    inventory_item_id: str,
    location_id: str,
    quantity: int,
    reason: str = "correction",
    name: str = "available",
) -> dict:
    """Set inventory quantity to an absolute value."""
    item_gid = _ensure_gid(inventory_item_id, "InventoryItem")
    loc_gid = _ensure_gid(location_id, "Location")

    input_data = {
        "reason": reason,
        "name": name,
        "ignoreCompareQuantity": True,
        "quantities": [
            {
                "inventoryItemId": item_gid,
                "locationId": loc_gid,
                "quantity": quantity,
            }
        ],
    }

    result = client.execute(SET_QUANTITIES_MUTATION, {"input": input_data})
    payload = result["data"]["inventorySetQuantities"]
    if payload["userErrors"]:
        errors = "; ".join(e["message"] for e in payload["userErrors"])
        raise ShopifyAPIError(f"Inventory set failed: {errors}")
    return payload
