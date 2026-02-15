"""Market discovery utilities.

Find and filter active Polymarket markets.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rich.console import Console
from rich.table import Table

from polybacker.client import PolymarketClient

logger = logging.getLogger(__name__)
console = Console()


def discover_markets(
    client: PolymarketClient,
    limit: int = 20,
    search: str | None = None,
    min_volume: float = 0,
):
    """Discover and display active markets.

    Args:
        client: Initialized PolymarketClient.
        limit: Max markets to display.
        search: Optional search keyword.
        min_volume: Minimum volume in USDC.
    """
    console.print("[bold]Fetching markets...[/bold]")

    if search:
        markets = client.search_markets(search, limit=limit)
        console.print(f"Search results for '{search}':")
    else:
        markets = client.get_active_markets(limit=100)

    # Filter by volume
    if min_volume > 0:
        markets = [m for m in markets if float(m.get("volume", 0) or 0) >= min_volume]

    # Sort by volume descending
    markets.sort(key=lambda m: float(m.get("volume", 0) or 0), reverse=True)
    markets = markets[:limit]

    if not markets:
        console.print("[yellow]No markets found matching your criteria.[/yellow]")
        return

    # Display table
    table = Table(title=f"Active Markets ({len(markets)})")
    table.add_column("#", style="dim", width=4)
    table.add_column("Market", max_width=50)
    table.add_column("Volume", justify="right", style="green")
    table.add_column("YES", justify="right", style="cyan")
    table.add_column("NO", justify="right", style="cyan")
    table.add_column("Spread", justify="right")

    for i, market in enumerate(markets, 1):
        tokens = market.get("tokens", [])
        yes_price = "—"
        no_price = "—"
        spread = "—"

        if len(tokens) >= 2:
            yp = float(tokens[0].get("price", 0) or 0)
            np = float(tokens[1].get("price", 0) or 0)
            yes_price = f"${yp:.2f}"
            no_price = f"${np:.2f}"
            combined = yp + np
            if combined > 0:
                gap = abs(1.0 - combined)
                spread = f"${gap:.4f}"

        volume = float(market.get("volume", 0) or 0)

        table.add_row(
            str(i),
            (market.get("question", "Unknown"))[:50],
            f"${volume:,.0f}",
            yes_price,
            no_price,
            spread,
        )

    console.print(table)

    # Export option
    export_path = Path("token_ids.json")
    token_data = []
    for market in markets:
        entry = {
            "question": market.get("question"),
            "slug": market.get("slug"),
            "condition_id": market.get("condition_id"),
            "tokens": [
                {
                    "outcome": t.get("outcome"),
                    "token_id": t.get("token_id"),
                    "price": t.get("price"),
                }
                for t in market.get("tokens", [])
            ],
        }
        token_data.append(entry)

    export_path.write_text(json.dumps(token_data, indent=2))
    console.print(f"\nToken IDs exported to [cyan]{export_path}[/cyan]")


def find_whales(
    client: PolymarketClient,
    condition_id: str,
    min_position: float = 1000,
    limit: int = 20,
) -> list[dict]:
    """Find top holders in a specific market.

    Args:
        client: Initialized PolymarketClient.
        condition_id: The market's condition ID.
        min_position: Minimum position size in USDC.
        limit: Max holders to return.

    Returns:
        List of holder dicts.
    """
    holders = client.get_market_holders(condition_id, limit=limit)

    table = Table(title="Top Holders")
    table.add_column("Rank", style="dim", width=5)
    table.add_column("Address", style="cyan")
    table.add_column("Position", justify="right", style="green")

    whales = []
    for i, holder in enumerate(holders, 1):
        position = float(holder.get("position_size", 0) or 0)
        if position < min_position:
            continue

        address = holder.get("user_address", "unknown")
        table.add_row(
            str(i),
            address,
            f"${position:,.2f}",
        )
        whales.append({"address": address, "position_size": position})

    console.print(table)
    return whales
