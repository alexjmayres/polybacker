"""CLI interface for Polybacker."""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

console = Console()


def _setup_logging(verbose: bool = False):
    """Configure logging with Rich handler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%H:%M:%S]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("web3").setLevel(logging.WARNING)
    logging.getLogger("py_clob_client").setLevel(logging.WARNING)


def _load_settings():
    """Load settings with error handling."""
    try:
        from polybacker.config import load_settings
        return load_settings()
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        console.print("Make sure you have a .env file. Copy .env.example to .env and fill in your values.")
        sys.exit(1)


def _init_client(settings):
    """Initialize the Polymarket client with error handling."""
    try:
        from polybacker.client import PolymarketClient
        return PolymarketClient(settings)
    except Exception as e:
        console.print(f"[red]Error connecting to Polymarket:[/red] {e}")
        console.print("Check your private key and network connection.")
        sys.exit(1)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose):
    """Polybacker — Polymarket copy trading & arbitrage bot."""
    _setup_logging(verbose)


# =============================================================================
# Copy Trading Commands
# =============================================================================

@cli.group()
def copy():
    """Copy trading commands."""
    pass


@copy.command("start")
@click.option("--dry-run", is_flag=True, help="Monitor without placing real trades")
@click.option("--traders-file", default="traders.txt", help="Path to traders file")
def copy_start(dry_run, traders_file):
    """Start the copy trading bot."""
    settings = _load_settings()
    client = _init_client(settings)

    from polybacker.copy_trader import CopyTrader

    trader = CopyTrader(settings=settings, client=client, dry_run=dry_run)
    trader.load_traders_from_file(traders_file)

    traders = trader.get_traders()
    if not traders:
        console.print("[red]No traders to follow![/red]")
        console.print("Add addresses with: polybacker copy add 0x...")
        console.print(f"Or add them to {traders_file}")
        return

    console.print(f"\n[bold green]Polybacker Copy Trader[/bold green]")
    console.print(f"Following [cyan]{len(traders)}[/cyan] traders")
    if dry_run:
        console.print("[yellow]DRY RUN — no real trades will be placed[/yellow]")
    console.print("")

    trader.run()


@copy.command("add")
@click.argument("address")
@click.option("--alias", "-a", default="", help="Friendly name for this trader")
def copy_add(address, alias):
    """Add a trader address to follow."""
    settings = _load_settings()

    from polybacker import db
    db.init_db(settings.db_path)

    if not address.startswith("0x") or len(address) != 42:
        console.print(f"[red]Invalid address:[/red] {address}")
        console.print("Address must be 42 characters starting with 0x")
        return

    if db.add_trader(settings.db_path, address, alias):
        console.print(f"[green]Added:[/green] {address}" + (f" ({alias})" if alias else ""))
    else:
        console.print(f"[yellow]Already following:[/yellow] {address}")


@copy.command("remove")
@click.argument("address")
def copy_remove(address):
    """Stop following a trader."""
    settings = _load_settings()

    from polybacker import db
    db.init_db(settings.db_path)

    if db.remove_trader(settings.db_path, address):
        console.print(f"[green]Removed:[/green] {address}")
    else:
        console.print(f"[yellow]Not found:[/yellow] {address}")


@copy.command("list")
def copy_list():
    """Show all followed traders."""
    settings = _load_settings()

    from polybacker import db
    db.init_db(settings.db_path)

    traders = db.get_active_traders(settings.db_path)
    if not traders:
        console.print("[yellow]No traders being followed.[/yellow]")
        console.print("Add with: polybacker copy add 0x...")
        return

    table = Table(title="Followed Traders")
    table.add_column("Address", style="cyan")
    table.add_column("Alias", style="white")
    table.add_column("Trades Copied", justify="right")
    table.add_column("Total Spent", justify="right", style="green")
    table.add_column("Added", style="dim")

    for t in traders:
        table.add_row(
            t["address"][:10] + "..." + t["address"][-6:],
            t["alias"] or "—",
            str(t["total_copied"]),
            f"${t['total_spent']:.2f}",
            t["added_at"][:10],
        )

    console.print(table)


@copy.command("stats")
def copy_stats():
    """Show copy trading statistics."""
    settings = _load_settings()

    from polybacker import db
    db.init_db(settings.db_path)

    stats = db.get_copy_stats(settings.db_path)
    daily = db.get_daily_spend(settings.db_path, strategy="copy")

    console.print("\n[bold]Copy Trading Stats[/bold]")
    console.print(f"  Total trades copied:  [cyan]{stats['total_trades']}[/cyan]")
    console.print(f"  Total spent:          [green]${stats['total_spent']:.2f}[/green]")
    console.print(f"  Failed trades:        [red]{stats['failed_trades']}[/red]")
    console.print(f"  Unique traders:       [cyan]{stats['unique_traders_copied']}[/cyan]")
    console.print(f"  Spent today:          [yellow]${daily:.2f}[/yellow] / ${settings.max_daily_spend:.2f}")
    console.print("")

    # Recent trades
    recent = db.get_trades(settings.db_path, strategy="copy", limit=10)
    if recent:
        table = Table(title="Recent Copy Trades")
        table.add_column("Time", style="dim")
        table.add_column("Market")
        table.add_column("Side")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("From", style="cyan")
        table.add_column("Status")

        for t in recent:
            status_style = "green" if t["status"] == "executed" else (
                "yellow" if t["status"] == "dry_run" else "red"
            )
            table.add_row(
                t["timestamp"][:19],
                (t["market"] or "—")[:40],
                t["side"],
                f"${t['amount']:.2f}",
                (t["copied_from"] or "—")[:10] + "...",
                f"[{status_style}]{t['status']}[/{status_style}]",
            )
        console.print(table)


@copy.command("trades")
@click.option("--limit", "-n", default=20, help="Number of trades to show")
def copy_trades(limit):
    """Show recent copied trades."""
    settings = _load_settings()

    from polybacker import db
    db.init_db(settings.db_path)

    trades = db.get_trades(settings.db_path, strategy="copy", limit=limit)
    if not trades:
        console.print("[yellow]No copy trades yet.[/yellow]")
        return

    table = Table(title=f"Last {min(limit, len(trades))} Copy Trades")
    table.add_column("Time", style="dim")
    table.add_column("Market")
    table.add_column("Side")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("From", style="cyan")
    table.add_column("Status")

    for t in trades:
        status_style = "green" if t["status"] == "executed" else (
            "yellow" if t["status"] == "dry_run" else "red"
        )
        table.add_row(
            t["timestamp"][:19],
            (t["market"] or "—")[:40],
            t["side"],
            f"${t['amount']:.2f}",
            (t["copied_from"] or "—")[:10] + "...",
            f"[{status_style}]{t['status']}[/{status_style}]",
        )
    console.print(table)


# =============================================================================
# Arbitrage Commands
# =============================================================================

@cli.command("arb")
@click.option("--dry-run", is_flag=True, help="Scan without placing trades")
def arb(dry_run):
    """Start the arbitrage scanner."""
    settings = _load_settings()
    client = _init_client(settings)

    from polybacker.arbitrage import ArbitrageScanner

    scanner = ArbitrageScanner(settings=settings, client=client, dry_run=dry_run)

    console.print(f"\n[bold green]Polybacker Arbitrage Scanner[/bold green]")
    console.print(f"Min profit: [cyan]{settings.min_profit_pct}%[/cyan]")
    console.print(f"Trade amount: [cyan]${settings.trade_amount}[/cyan]")
    if dry_run:
        console.print("[yellow]DRY RUN — no real trades will be placed[/yellow]")
    console.print("")

    scanner.run()


# =============================================================================
# Market Discovery
# =============================================================================

@cli.command("discover")
@click.option("--limit", "-n", default=20, help="Number of markets to show")
@click.option("--search", "-s", default=None, help="Search keyword")
@click.option("--min-volume", default=1000.0, help="Minimum volume in USDC")
def discover(limit, search, min_volume):
    """Discover active Polymarket markets."""
    settings = _load_settings()
    client = _init_client(settings)

    from polybacker.market_discovery import discover_markets

    discover_markets(client, limit=limit, search=search, min_volume=min_volume)


# =============================================================================
# Dashboard Server
# =============================================================================

@cli.command("server")
@click.option("--port", "-p", default=5000, help="Server port")
@click.option("--host", "-h", default="0.0.0.0", help="Server host")
def server(port, host):
    """Start the web dashboard server."""
    settings = _load_settings()

    console.print(f"\n[bold green]Polybacker Dashboard[/bold green]")
    console.print(f"Open [link=http://localhost:{port}]http://localhost:{port}[/link] in your browser")
    console.print("")

    from polybacker.server import create_app
    app, socketio = create_app(settings)
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    cli()
