"""
Utility script to discover active Polymarket markets and get token IDs
"""

import requests
from typing import List, Dict
import json


def get_active_markets(limit: int = 20) -> List[Dict]:
    """
    Fetch active markets from Polymarket Gamma API
    
    Args:
        limit: Number of markets to fetch
        
    Returns:
        List of market data
    """
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "limit": limit,
        "active": "true"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching markets: {e}")
        return []


def get_market_by_slug(slug: str) -> Dict:
    """
    Get a specific market by its slug
    
    Args:
        slug: Market slug (from URL)
        
    Returns:
        Market data
    """
    url = f"https://gamma-api.polymarket.com/markets/{slug}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching market: {e}")
        return {}


def display_markets(markets: List[Dict], detailed: bool = False):
    """
    Display market information in a readable format
    
    Args:
        markets: List of market data
        detailed: Show detailed information
    """
    print(f"\n{'='*80}")
    print(f"Found {len(markets)} Active Markets")
    print(f"{'='*80}\n")
    
    for i, market in enumerate(markets, 1):
        print(f"{i}. {market.get('question', 'N/A')}")
        print(f"   Description: {market.get('description', 'N/A')[:100]}...")
        print(f"   Category: {market.get('category', 'N/A')}")
        print(f"   Volume: ${market.get('volume', 0):,.2f}")
        print(f"   Liquidity: ${market.get('liquidity', 0):,.2f}")
        
        # Token information
        tokens = market.get('tokens', [])
        if tokens:
            print(f"   Tokens:")
            for token in tokens:
                outcome = token.get('outcome', 'N/A')
                token_id = token.get('token_id', 'N/A')
                price = token.get('price', 0)
                print(f"     - {outcome}: {token_id[:16]}... (Price: ${price:.4f})")
        
        # Additional details if requested
        if detailed:
            print(f"   Market ID: {market.get('condition_id', 'N/A')}")
            print(f"   End Date: {market.get('end_date_iso', 'N/A')}")
            print(f"   Closed: {market.get('closed', False)}")
            print(f"   Slug: {market.get('slug', 'N/A')}")
        
        print()


def search_markets(query: str, limit: int = 10) -> List[Dict]:
    """
    Search for markets by keyword
    
    Args:
        query: Search query
        limit: Max results
        
    Returns:
        List of matching markets
    """
    markets = get_active_markets(limit=100)
    
    # Filter by query
    filtered = [
        m for m in markets 
        if query.lower() in m.get('question', '').lower() 
        or query.lower() in m.get('description', '').lower()
    ]
    
    return filtered[:limit]


def get_high_volume_markets(min_volume: float = 1000.0, limit: int = 10) -> List[Dict]:
    """
    Get markets with high trading volume
    
    Args:
        min_volume: Minimum volume in USDC
        limit: Max results
        
    Returns:
        List of high-volume markets
    """
    markets = get_active_markets(limit=100)
    
    # Filter by volume and sort
    high_volume = [m for m in markets if m.get('volume', 0) >= min_volume]
    high_volume.sort(key=lambda x: x.get('volume', 0), reverse=True)
    
    return high_volume[:limit]


def export_token_ids(markets: List[Dict], filename: str = "token_ids.json"):
    """
    Export token IDs to a JSON file
    
    Args:
        markets: List of market data
        filename: Output filename
    """
    token_data = []
    
    for market in markets:
        market_info = {
            "question": market.get('question'),
            "slug": market.get('slug'),
            "tokens": []
        }
        
        for token in market.get('tokens', []):
            market_info["tokens"].append({
                "outcome": token.get('outcome'),
                "token_id": token.get('token_id'),
                "price": token.get('price')
            })
        
        token_data.append(market_info)
    
    with open(filename, 'w') as f:
        json.dump(token_data, f, indent=2)
    
    print(f"\nToken IDs exported to {filename}")


def main():
    """
    Main function demonstrating different queries
    """
    print("Polymarket Markets Explorer")
    print("="*80)
    
    # Example 1: Get top active markets
    print("\n1. TOP 10 ACTIVE MARKETS")
    markets = get_active_markets(limit=10)
    display_markets(markets)
    
    # Example 2: Search for specific topics
    print("\n2. SEARCHING FOR 'TRUMP' MARKETS")
    trump_markets = search_markets("trump", limit=5)
    display_markets(trump_markets)
    
    # Example 3: High volume markets
    print("\n3. HIGH VOLUME MARKETS (>$10,000)")
    high_vol = get_high_volume_markets(min_volume=10000, limit=5)
    display_markets(high_vol, detailed=True)
    
    # Example 4: Export token IDs
    if markets:
        export_token_ids(markets[:10])
    
    # Show example of how to use the token IDs
    print("\n" + "="*80)
    print("HOW TO USE THESE TOKEN IDs IN YOUR BOT:")
    print("="*80)
    if markets and markets[0].get('tokens'):
        first_market = markets[0]
        tokens = first_market.get('tokens', [])
        if len(tokens) >= 2:
            yes_token = tokens[0].get('token_id')
            no_token = tokens[1].get('token_id')
            
            print(f"""
Example usage in polymarket_bot.py:

from polymarket_bot import PolymarketBot
from py_clob_client.order_builder.constants import BUY

bot = PolymarketBot(private_key="your_key")

# Monitor this market
market_data = bot.get_market_data("{yes_token}")
print(f"Current price: ${{market_data['midpoint']}}")

# Check for arbitrage
arb = bot.check_arbitrage_opportunity(
    yes_token_id="{yes_token}",
    no_token_id="{no_token}"
)

# Place an order
bot.place_market_order(
    token_id="{yes_token}",
    amount=10.0,
    side=BUY
)
""")


if __name__ == "__main__":
    main()
