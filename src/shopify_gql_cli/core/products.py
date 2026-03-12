"""Product queries and mutations."""

from shopify_gql_cli.core.client import ShopifyClient

LIST_PRODUCTS_QUERY = """
query($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query) {
    edges {
      node {
        id
        title
        handle
        status
        productType
        vendor
        totalInventory
        priceRangeV2 {
          minVariantPrice { amount currencyCode }
          maxVariantPrice { amount currencyCode }
        }
        variants(first: 5) {
          edges {
            node {
              id
              title
              sku
              price
              inventoryQuantity
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

GET_PRODUCT_QUERY = """
query($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    descriptionHtml
    status
    productType
    vendor
    tags
    totalInventory
    createdAt
    updatedAt
    priceRangeV2 {
      minVariantPrice { amount currencyCode }
      maxVariantPrice { amount currencyCode }
    }
    options { id name values }
    variants(first: 100) {
      edges {
        node {
          id
          title
          sku
          price
          compareAtPrice
          inventoryQuantity
          selectedOptions { name value }
          inventoryItem { id }
        }
      }
    }
    images(first: 10) {
      edges {
        node {
          id
          url
          altText
        }
      }
    }
  }
}
"""

CREATE_PRODUCT_MUTATION = """
mutation($product: ProductCreateInput!) {
  productCreate(product: $product) {
    product {
      id
      title
      handle
      status
    }
    userErrors { field message }
  }
}
"""

UPDATE_PRODUCT_MUTATION = """
mutation($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product {
      id
      title
      handle
      status
    }
    userErrors { field message }
  }
}
"""

DELETE_PRODUCT_MUTATION = """
mutation($input: ProductDeleteInput!) {
  productDelete(input: $input) {
    deletedProductId
    userErrors { field message }
  }
}
"""


def _ensure_gid(raw_id: str, resource: str = "Product") -> str:
    if raw_id.startswith("gid://"):
        return raw_id
    return f"gid://shopify/{resource}/{raw_id}"


def list_products(
    client: ShopifyClient,
    first: int = 10,
    after: str | None = None,
    query: str | None = None,
) -> dict:
    """Query products with optional search string."""
    result = client.execute(
        LIST_PRODUCTS_QUERY, {"first": first, "after": after, "query": query}
    )
    return result["data"]["products"]


def get_product(client: ShopifyClient, product_id: str) -> dict:
    """Get a single product by ID."""
    gid = _ensure_gid(product_id, "Product")
    result = client.execute(GET_PRODUCT_QUERY, {"id": gid})
    return result["data"]["product"]


def create_product(
    client: ShopifyClient,
    title: str,
    product_type: str | None = None,
    vendor: str | None = None,
    description_html: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
) -> dict:
    """Create a new product."""
    product_input: dict = {"title": title}
    if product_type:
        product_input["productType"] = product_type
    if vendor:
        product_input["vendor"] = vendor
    if description_html:
        product_input["descriptionHtml"] = description_html
    if tags:
        product_input["tags"] = tags
    if status:
        product_input["status"] = status.upper()

    result = client.execute(CREATE_PRODUCT_MUTATION, {"product": product_input})
    payload = result["data"]["productCreate"]
    if payload["userErrors"]:
        from shopify_gql_cli.core.client import ShopifyAPIError
        errors = "; ".join(e["message"] for e in payload["userErrors"])
        raise ShopifyAPIError(f"Product create failed: {errors}")
    return payload


def update_product(
    client: ShopifyClient,
    product_id: str,
    title: str | None = None,
    product_type: str | None = None,
    vendor: str | None = None,
    description_html: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
) -> dict:
    """Update an existing product."""
    gid = _ensure_gid(product_id, "Product")
    product_input: dict = {"id": gid}
    if title:
        product_input["title"] = title
    if product_type:
        product_input["productType"] = product_type
    if vendor:
        product_input["vendor"] = vendor
    if description_html:
        product_input["descriptionHtml"] = description_html
    if tags is not None:
        product_input["tags"] = tags
    if status:
        product_input["status"] = status.upper()

    result = client.execute(UPDATE_PRODUCT_MUTATION, {"product": product_input})
    payload = result["data"]["productUpdate"]
    if payload["userErrors"]:
        from shopify_gql_cli.core.client import ShopifyAPIError
        errors = "; ".join(e["message"] for e in payload["userErrors"])
        raise ShopifyAPIError(f"Product update failed: {errors}")
    return payload


def delete_product(client: ShopifyClient, product_id: str) -> dict:
    """Delete a product."""
    gid = _ensure_gid(product_id, "Product")
    result = client.execute(DELETE_PRODUCT_MUTATION, {"input": {"id": gid}})
    payload = result["data"]["productDelete"]
    if payload["userErrors"]:
        from shopify_gql_cli.core.client import ShopifyAPIError
        errors = "; ".join(e["message"] for e in payload["userErrors"])
        raise ShopifyAPIError(f"Product delete failed: {errors}")
    return payload
