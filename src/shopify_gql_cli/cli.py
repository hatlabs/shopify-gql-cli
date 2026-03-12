"""Shopify Admin GraphQL API CLI — Click-based command interface with REPL."""

import json
import sys

import click

from shopify_gql_cli.core.client import ShopifyAPIError, make_client
from shopify_gql_cli.core import (
    customers,
    graphql,
    inventory,
    orders,
    products,
    shop,
)


class CliContext:
    """Shared state passed via Click context."""

    def __init__(self, json_output: bool, store: str | None, token: str | None):
        self.json_output = json_output
        self.store = store
        self.token = token
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = make_client(store=self.store, token=self.token)
        return self._client


pass_ctx = click.make_pass_decorator(CliContext, ensure=True)


def _output(ctx: CliContext, data, headers: list[str] | None = None, rows_fn=None):
    """Print data as JSON or human-readable table."""
    if ctx.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if headers and rows_fn:
        from shopify_gql_cli.utils.repl_skin import ReplSkin
        skin = ReplSkin("shopify_gql_cli")
        skin.table(headers, rows_fn(data))
    else:
        click.echo(json.dumps(data, indent=2, default=str))


def _print_edges(ctx, data, headers, row_fn):
    """Print a connection's edges as a table."""
    edges = data.get("edges", [])
    nodes = [e["node"] for e in edges]
    page_info = data.get("pageInfo", {})

    if ctx.json_output:
        click.echo(json.dumps({"nodes": nodes, "pageInfo": page_info}, indent=2, default=str))
        return

    from shopify_gql_cli.utils.repl_skin import ReplSkin
    skin = ReplSkin("shopify_gql_cli")

    rows = [row_fn(n) for n in nodes]
    skin.table(headers, rows)

    if page_info.get("hasNextPage"):
        skin.hint(f"\n  More results available. Use --after {page_info['endCursor']}")


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--store", envvar="SHOPIFY_STORE_URL", help="Shopify store URL.")
@click.option("--token", envvar="SHOPIFY_ACCESS_TOKEN", help="Shopify access token.")
@click.pass_context
def cli(ctx, json_output, store, token):
    """Shopify Admin GraphQL API CLI."""
    ctx.obj = CliContext(json_output=json_output, store=store, token=token)

    if ctx.invoked_subcommand is None:
        _run_repl(ctx.obj)


def _run_repl(ctx: CliContext):
    """Interactive REPL mode."""
    from shopify_gql_cli.utils.repl_skin import ReplSkin

    skin = ReplSkin("shopify_gql_cli")
    skin.print_banner()

    pt_session = skin.create_prompt_session()

    commands = {
        "shop info": "Show shop information",
        "shop locations": "List locations",
        "orders list": "List orders (--first N --query Q)",
        "orders get <id>": "Get order details",
        "orders cancel <id>": "Cancel an order",
        "orders close <id>": "Close an order",
        "products list": "List products",
        "products get <id>": "Get product details",
        "products create <title>": "Create a product",
        "products delete <id>": "Delete a product",
        "customers list": "List customers",
        "customers get <id>": "Get customer details",
        "inventory levels": "List inventory levels",
        "inventory adjust": "Adjust inventory quantity",
        "inventory set": "Set inventory quantity",
        "graphql <query>": "Execute raw GraphQL",
        "help": "Show this help",
        "quit / exit": "Exit the REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue

        if line in ("quit", "exit", "q"):
            skin.print_goodbye()
            break

        if line == "help":
            skin.help(commands)
            continue

        # Parse and dispatch via Click
        args = line.split()
        if ctx.json_output:
            args = ["--json"] + args

        try:
            cli.main(args=args, standalone_mode=False, obj=ctx)
        except SystemExit:
            pass
        except ShopifyAPIError as e:
            skin.error(str(e))
        except click.UsageError as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# shop
# ---------------------------------------------------------------------------


@cli.group()
def shop_cmd():
    """Shop information."""


# Register as 'shop' (avoiding conflict with the module name in dispatch)
shop_cmd = cli.group(name="shop")(lambda: None)


@shop_cmd.command("info")
@pass_ctx
def shop_info(ctx):
    """Show shop information."""
    data = shop.get_shop_info(ctx.client)
    if ctx.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    from shopify_gql_cli.utils.repl_skin import ReplSkin
    skin = ReplSkin("shopify_gql_cli")
    items = {
        "Name": data.get("name", ""),
        "Email": data.get("email", ""),
        "Domain": data.get("myshopifyDomain", ""),
        "Primary domain": (data.get("primaryDomain") or {}).get("host", ""),
        "Plan": (data.get("plan") or {}).get("displayName", ""),
        "Currency": data.get("currencyCode", ""),
        "Timezone": data.get("timezoneAbbreviation", ""),
    }
    skin.status_block(items, title="Shop Info")


@shop_cmd.command("locations")
@click.option("--first", default=10, type=click.IntRange(1, 250), help="Number of results.")
@click.option("--after", default=None, help="Pagination cursor.")
@pass_ctx
def shop_locations(ctx, first, after):
    """List shop locations."""
    data = shop.get_locations(ctx.client, first=first, after=after)
    _print_edges(
        ctx,
        data,
        ["ID", "Name", "Active", "City", "Country"],
        lambda n: [
            n["id"].split("/")[-1],
            n["name"],
            "Yes" if n["isActive"] else "No",
            (n.get("address") or {}).get("city", ""),
            (n.get("address") or {}).get("country", ""),
        ],
    )


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------


@cli.group(name="orders")
def orders_cmd():
    """Order management."""


@orders_cmd.command("list")
@click.option("--first", default=10, type=click.IntRange(1, 250), help="Number of results.")
@click.option("--after", default=None, help="Pagination cursor.")
@click.option("--query", "-q", default=None, help="Search query string.")
@pass_ctx
def orders_list(ctx, first, after, query):
    """List orders."""
    data = orders.list_orders(ctx.client, first=first, after=after, query=query)
    _print_edges(
        ctx,
        data,
        ["Name", "Status", "Fulfillment", "Total", "Customer", "Created"],
        lambda n: [
            n["name"],
            n.get("displayFinancialStatus", ""),
            n.get("displayFulfillmentStatus", ""),
            (n.get("totalPriceSet") or {}).get("shopMoney", {}).get("amount", ""),
            (n.get("customer") or {}).get("displayName", "N/A"),
            n.get("createdAt", "")[:10],
        ],
    )


@orders_cmd.command("get")
@click.argument("order_id")
@pass_ctx
def orders_get(ctx, order_id):
    """Get order details."""
    data = orders.get_order(ctx.client, order_id)
    if not data:
        click.echo("Order not found.", err=True)
        return

    if ctx.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    from shopify_gql_cli.utils.repl_skin import ReplSkin
    skin = ReplSkin("shopify_gql_cli")
    total = (data.get("totalPriceSet") or {}).get("shopMoney", {})
    items = {
        "Order": data.get("name", ""),
        "ID": data["id"],
        "Created": data.get("createdAt", "")[:19],
        "Financial": data.get("displayFinancialStatus", ""),
        "Fulfillment": data.get("displayFulfillmentStatus", ""),
        "Total": f"{total.get('amount', '')} {total.get('currencyCode', '')}",
        "Customer": (data.get("customer") or {}).get("displayName", "N/A"),
        "Note": data.get("note") or "",
    }
    skin.status_block(items, title="Order Details")

    line_items = [e["node"] for e in (data.get("lineItems", {}).get("edges", []))]
    if line_items:
        skin.section("Line Items")
        rows = []
        for li in line_items:
            price = (li.get("originalUnitPriceSet") or {}).get("shopMoney", {})
            rows.append([
                li.get("title", "")[:40],
                li.get("sku", ""),
                str(li.get("quantity", "")),
                price.get("amount", ""),
            ])
        skin.table(["Title", "SKU", "Qty", "Unit Price"], rows)


@orders_cmd.command("cancel")
@click.argument("order_id")
@click.option("--reason", default=None, help="Cancellation reason (CUSTOMER, DECLINED, FRAUD, INVENTORY, OTHER, STAFF).")
@click.option("--notify/--no-notify", default=False, help="Notify customer.")
@click.option("--staff-note", default=None, help="Internal staff note.")
@pass_ctx
def orders_cancel(ctx, order_id, reason, notify, staff_note):
    """Cancel an order."""
    data = orders.cancel_order(
        ctx.client, order_id, reason=reason, notify_customer=notify, staff_note=staff_note
    )
    _output(ctx, data)


@orders_cmd.command("close")
@click.argument("order_id")
@pass_ctx
def orders_close(ctx, order_id):
    """Close an order."""
    data = orders.close_order(ctx.client, order_id)
    _output(ctx, data)


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------


@cli.group(name="products")
def products_cmd():
    """Product management."""


@products_cmd.command("list")
@click.option("--first", default=10, type=click.IntRange(1, 250), help="Number of results.")
@click.option("--after", default=None, help="Pagination cursor.")
@click.option("--query", "-q", default=None, help="Search query string.")
@pass_ctx
def products_list(ctx, first, after, query):
    """List products."""
    data = products.list_products(ctx.client, first=first, after=after, query=query)
    _print_edges(
        ctx,
        data,
        ["ID", "Title", "Status", "Type", "Inventory", "Price Range"],
        lambda n: [
            n["id"].split("/")[-1],
            n.get("title", "")[:35],
            n.get("status", ""),
            n.get("productType", ""),
            str(n.get("totalInventory", "")),
            _price_range(n),
        ],
    )


def _price_range(product: dict) -> str:
    pr = product.get("priceRangeV2") or {}
    min_p = (pr.get("minVariantPrice") or {}).get("amount", "")
    max_p = (pr.get("maxVariantPrice") or {}).get("amount", "")
    if min_p == max_p:
        return min_p
    return f"{min_p}-{max_p}"


@products_cmd.command("get")
@click.argument("product_id")
@pass_ctx
def products_get(ctx, product_id):
    """Get product details."""
    data = products.get_product(ctx.client, product_id)
    if not data:
        click.echo("Product not found.", err=True)
        return

    if ctx.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    from shopify_gql_cli.utils.repl_skin import ReplSkin
    skin = ReplSkin("shopify_gql_cli")
    items = {
        "Title": data.get("title", ""),
        "ID": data["id"],
        "Handle": data.get("handle", ""),
        "Status": data.get("status", ""),
        "Type": data.get("productType", ""),
        "Vendor": data.get("vendor", ""),
        "Tags": ", ".join(data.get("tags") or []),
        "Inventory": str(data.get("totalInventory", "")),
    }
    skin.status_block(items, title="Product Details")

    variants = [e["node"] for e in (data.get("variants", {}).get("edges", []))]
    if variants:
        skin.section("Variants")
        rows = []
        for v in variants:
            rows.append([
                v.get("title", "")[:30],
                v.get("sku", ""),
                v.get("price", ""),
                str(v.get("inventoryQuantity", "")),
            ])
        skin.table(["Title", "SKU", "Price", "Inventory"], rows)


@products_cmd.command("create")
@click.argument("title")
@click.option("--type", "product_type", default=None, help="Product type.")
@click.option("--vendor", default=None, help="Product vendor.")
@click.option("--description", "description_html", default=None, help="HTML description.")
@click.option("--tags", default=None, help="Comma-separated tags.")
@click.option("--status", default=None, type=click.Choice(["ACTIVE", "DRAFT", "ARCHIVED"], case_sensitive=False))
@pass_ctx
def products_create(ctx, title, product_type, vendor, description_html, tags, status):
    """Create a product."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    data = products.create_product(
        ctx.client,
        title=title,
        product_type=product_type,
        vendor=vendor,
        description_html=description_html,
        tags=tag_list,
        status=status,
    )
    _output(ctx, data)


@products_cmd.command("update")
@click.argument("product_id")
@click.option("--title", default=None, help="New title.")
@click.option("--type", "product_type", default=None, help="Product type.")
@click.option("--vendor", default=None, help="Product vendor.")
@click.option("--description", "description_html", default=None, help="HTML description.")
@click.option("--tags", default=None, help="Comma-separated tags (replaces all).")
@click.option("--status", default=None, type=click.Choice(["ACTIVE", "DRAFT", "ARCHIVED"], case_sensitive=False))
@pass_ctx
def products_update(ctx, product_id, title, product_type, vendor, description_html, tags, status):
    """Update a product."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    data = products.update_product(
        ctx.client,
        product_id=product_id,
        title=title,
        product_type=product_type,
        vendor=vendor,
        description_html=description_html,
        tags=tag_list,
        status=status,
    )
    _output(ctx, data)


@products_cmd.command("delete")
@click.argument("product_id")
@click.confirmation_option(prompt="Are you sure you want to delete this product?")
@pass_ctx
def products_delete(ctx, product_id):
    """Delete a product."""
    data = products.delete_product(ctx.client, product_id)
    _output(ctx, data)


# ---------------------------------------------------------------------------
# customers
# ---------------------------------------------------------------------------


@cli.group(name="customers")
def customers_cmd():
    """Customer management."""


@customers_cmd.command("list")
@click.option("--first", default=10, type=click.IntRange(1, 250), help="Number of results.")
@click.option("--after", default=None, help="Pagination cursor.")
@click.option("--query", "-q", default=None, help="Search query string.")
@pass_ctx
def customers_list(ctx, first, after, query):
    """List customers."""
    data = customers.list_customers(ctx.client, first=first, after=after, query=query)
    _print_edges(
        ctx,
        data,
        ["ID", "Name", "Email", "Orders", "Spent", "State"],
        lambda n: [
            n["id"].split("/")[-1],
            n.get("displayName", ""),
            n.get("email", ""),
            str(n.get("numberOfOrders", "")),
            (n.get("amountSpent") or {}).get("amount", ""),
            n.get("state", ""),
        ],
    )


@customers_cmd.command("get")
@click.argument("customer_id")
@pass_ctx
def customers_get(ctx, customer_id):
    """Get customer details."""
    data = customers.get_customer(ctx.client, customer_id)
    if not data:
        click.echo("Customer not found.", err=True)
        return

    if ctx.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    from shopify_gql_cli.utils.repl_skin import ReplSkin
    skin = ReplSkin("shopify_gql_cli")
    spent = (data.get("amountSpent") or {})
    addr = data.get("defaultAddress") or {}
    items = {
        "Name": data.get("displayName", ""),
        "ID": data["id"],
        "Email": data.get("email", ""),
        "Phone": data.get("phone", "") or "",
        "State": data.get("state", ""),
        "Orders": str(data.get("numberOfOrders", "")),
        "Total spent": f"{spent.get('amount', '')} {spent.get('currencyCode', '')}",
        "Address": f"{addr.get('address1', '')}, {addr.get('city', '')}, {addr.get('country', '')}",
        "Tags": ", ".join(data.get("tags") or []),
        "Note": data.get("note") or "",
    }
    skin.status_block(items, title="Customer Details")


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------


@cli.group(name="inventory")
def inventory_cmd():
    """Inventory management."""


@inventory_cmd.command("levels")
@click.option("--first", default=10, type=click.IntRange(1, 250), help="Number of results.")
@click.option("--after", default=None, help="Pagination cursor.")
@click.option("--query", "-q", default=None, help="Search query (e.g., SKU).")
@click.option("--item-id", default=None, help="Specific inventory item ID.")
@pass_ctx
def inventory_levels(ctx, first, after, query, item_id):
    """Show inventory levels."""
    if item_id:
        data = inventory.get_inventory_item_levels(ctx.client, item_id)
        if not data:
            click.echo("Inventory item not found.", err=True)
            return
        if ctx.json_output:
            click.echo(json.dumps(data, indent=2, default=str))
            return
        from shopify_gql_cli.utils.repl_skin import ReplSkin
        skin = ReplSkin("shopify_gql_cli")
        skin.info(f"SKU: {data.get('sku', 'N/A')}  Tracked: {data.get('tracked', False)}")
        levels = [e["node"] for e in (data.get("inventoryLevels", {}).get("edges", []))]
        rows = []
        for lv in levels:
            loc = (lv.get("location") or {}).get("name", "")
            qtys = {q["name"]: q["quantity"] for q in (lv.get("quantities") or [])}
            rows.append([loc, str(qtys.get("available", "")), str(qtys.get("on_hand", "")),
                         str(qtys.get("committed", "")), str(qtys.get("reserved", ""))])
        skin.table(["Location", "Available", "On Hand", "Committed", "Reserved"], rows)
        return

    data = inventory.get_inventory_levels(ctx.client, first=first, after=after, query=query)
    if ctx.json_output:
        edges = data.get("edges", [])
        nodes = [e["node"] for e in edges]
        click.echo(json.dumps({"nodes": nodes, "pageInfo": data.get("pageInfo", {})}, indent=2, default=str))
        return

    from shopify_gql_cli.utils.repl_skin import ReplSkin
    skin = ReplSkin("shopify_gql_cli")
    edges = data.get("edges", [])
    rows = []
    for edge in edges:
        item = edge["node"]
        sku = item.get("sku") or ""
        for lv_edge in (item.get("inventoryLevels", {}).get("edges", [])):
            lv = lv_edge["node"]
            loc = (lv.get("location") or {}).get("name", "")
            qtys = {q["name"]: q["quantity"] for q in (lv.get("quantities") or [])}
            rows.append([sku, loc, str(qtys.get("available", "")), str(qtys.get("on_hand", ""))])
    skin.table(["SKU", "Location", "Available", "On Hand"], rows)

    page_info = data.get("pageInfo", {})
    if page_info.get("hasNextPage"):
        skin.hint(f"\n  More results available. Use --after {page_info['endCursor']}")


@inventory_cmd.command("adjust")
@click.option("--item-id", required=True, help="Inventory item ID.")
@click.option("--location-id", required=True, help="Location ID.")
@click.option("--delta", required=True, type=int, help="Quantity change (positive or negative).")
@click.option("--reason", default="correction", help="Reason for adjustment.")
@click.option("--name", default="available", help="Quantity name (available, on_hand).")
@pass_ctx
def inventory_adjust(ctx, item_id, location_id, delta, reason, name):
    """Adjust inventory quantity by a delta."""
    data = inventory.adjust_inventory(
        ctx.client, item_id, location_id, delta, reason=reason, name=name
    )
    _output(ctx, data)


@inventory_cmd.command("set")
@click.option("--item-id", required=True, help="Inventory item ID.")
@click.option("--location-id", required=True, help="Location ID.")
@click.option("--quantity", required=True, type=int, help="Absolute quantity to set.")
@click.option("--reason", default="correction", help="Reason for change.")
@click.option("--name", default="available", help="Quantity name (available, on_hand).")
@pass_ctx
def inventory_set(ctx, item_id, location_id, quantity, reason, name):
    """Set inventory quantity to an absolute value."""
    data = inventory.set_inventory(
        ctx.client, item_id, location_id, quantity, reason=reason, name=name
    )
    _output(ctx, data)


# ---------------------------------------------------------------------------
# graphql
# ---------------------------------------------------------------------------


@cli.group(name="graphql")
def graphql_cmd():
    """Raw GraphQL query execution."""


@graphql_cmd.command("execute")
@click.argument("query")
@click.option("--variables", "-v", default=None, help="JSON string of variables.")
@pass_ctx
def graphql_execute(ctx, query, variables):
    """Execute a raw GraphQL query or mutation."""
    vars_dict = graphql.parse_variables(variables)
    data = graphql.execute_raw(ctx.client, query, variables=vars_dict)

    # Always output as JSON for raw queries — the structure is unpredictable
    click.echo(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    try:
        cli(standalone_mode=True)
    except ShopifyAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
