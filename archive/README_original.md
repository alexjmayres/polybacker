# Polymarket Trading Bot

An automated trading bot for Polymarket's prediction markets using the official CLOB (Central Limit Order Book) API.

## Features

- **Market Monitoring**: Track multiple markets in real-time
- **Arbitrage Detection**: Automatically detect risk-free arbitrage opportunities
- **Simple Momentum Strategy**: Trade based on recent price movements
- **Multiple Wallet Types**: Support for EOA, Magic wallets, and Gnosis Safe
- **Comprehensive Logging**: Track all bot activities and trades

## Prerequisites

- Python 3.9 or higher
- A Polygon wallet with USDC.e
- Polymarket account
- Basic understanding of prediction markets

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

### Getting Your Private Key

**For MetaMask/EOA wallets:**
1. Open MetaMask
2. Click the three dots → Account Details → Export Private Key
3. Enter your password and copy the key
4. Set `POLYMARKET_SIGNATURE_TYPE=0`

**For Magic/Email wallets:**
1. You'll need to extract your key from the Magic SDK
2. Set `POLYMARKET_SIGNATURE_TYPE=1`
3. Set your `POLYMARKET_FUNDER` address

### Setting Token Allowances

If using an EOA wallet (MetaMask), you must set token allowances before trading:

```python
from py_clob_client.client import ClobClient
from py_clob_client.exceptions import PolyApiException

client = ClobClient(
    "https://clob.polymarket.com",
    key=YOUR_PRIVATE_KEY,
    chain_id=137
)

# Set allowances
try:
    client.set_token_allowance(token_id, amount)
    print("Allowances set successfully")
except PolyApiException as e:
    print(f"Error: {e}")
```

## Getting Token IDs

You need token IDs to trade specific markets. Get them from the Gamma API:

```python
import requests

# Get all active markets
response = requests.get("https://gamma-api.polymarket.com/markets")
markets = response.json()

for market in markets[:5]:  # Show first 5
    print(f"Market: {market['question']}")
    print(f"YES Token: {market['tokens'][0]['token_id']}")
    print(f"NO Token: {market['tokens'][1]['token_id']}")
    print()
```

## Usage Examples

### Basic Market Monitoring

```python
from polymarket_bot import PolymarketBot

# Initialize bot
bot = PolymarketBot(
    private_key="your_private_key",
    signature_type=0  # EOA wallet
)

# Get market data
token_id = "your_token_id_here"
data = bot.get_market_data(token_id)
print(f"Current price: ${data['midpoint']}")
print(f"Spread: ${data['spread']}")
```

### Arbitrage Detection

```python
# Check for arbitrage between YES and NO tokens
yes_token = "yes_token_id"
no_token = "no_token_id"

arb = bot.check_arbitrage_opportunity(yes_token, no_token)
if arb:
    print(f"Arbitrage found! Profit: ${arb['profit']:.4f}")
    
    # Execute the trade
    success = bot.execute_arbitrage(arb, amount=10.0)
    if success:
        print("Arbitrage executed successfully!")
```

### Placing Orders

```python
from py_clob_client.order_builder.constants import BUY, SELL
from py_clob_client.clob_types import OrderType

# Place a market order
bot.place_market_order(
    token_id="your_token_id",
    amount=10.0,  # USDC
    side=BUY,
    order_type=OrderType.FOK  # Fill or Kill
)
```

### Running Continuous Monitoring

```python
# Monitor multiple markets
token_ids = [
    "token_id_1",
    "token_id_2",
    "token_id_3"
]

# Run monitoring loop (checks every 30 seconds)
bot.run_monitoring_loop(token_ids, interval=30)
```

## Trading Strategies

### 1. Arbitrage Strategy

The bot can detect when YES + NO token prices sum to less than $1.00, creating a risk-free arbitrage opportunity:

```
Market: "Will BTC exceed $100k by Dec 31?"
YES token @ $0.48
NO token @ $0.49
Combined: $0.97
Guaranteed payout: $1.00
Risk-free profit: $0.03 (3.09% return)
```

### 2. Momentum Strategy

Trade based on recent price movements:
- Buy when price is 2% below recent average
- Sell when price is 2% above recent average

### 3. Custom Strategy Template

```python
def custom_strategy(self, token_id: str) -> Optional[str]:
    """
    Implement your own trading logic here
    
    Returns:
        "BUY", "SELL", or None
    """
    market_data = self.get_market_data(token_id)
    
    # Your logic here
    if some_buy_condition:
        return BUY
    elif some_sell_condition:
        return SELL
    
    return None
```

## Risk Management

**Important considerations:**

1. **Start Small**: Test with small amounts first
2. **Set Position Limits**: Never risk more than you can afford to lose
3. **Monitor Liquidity**: Ensure markets have enough liquidity for your trades
4. **Gas Fees**: Consider Polygon gas fees in your profit calculations
5. **Slippage**: Market orders may execute at different prices than expected

## API Rate Limits

From the documentation:
- Free tier: ~100 requests per minute
- Higher volume users: Consider premium tiers

## Common Issues

### "Not enough balance/allowance" error
- Ensure your wallet has USDC.e on Polygon
- Set token allowances (for EOA wallets)

### Orders not executing
- Check that the market has sufficient liquidity
- Verify your order size meets minimum requirements
- Ensure your wallet is funded

### Slow performance
- Order signing can take ~1 second
- Use async operations for better performance
- Consider running on a VPS for 24/7 operation

## Advanced Features

### WebSocket Integration

For real-time updates, consider using WebSockets:

```python
# Example using websockets library
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"Update: {data}")

ws = websocket.WebSocketApp(
    "wss://clob-ws.polymarket.com",
    on_message=on_message
)
ws.run_forever()
```

### Backtesting

Test strategies on historical data before live trading:

```python
from py_clob_client.client import ClobClient

client = ClobClient("https://clob.polymarket.com")

# Get historical price data
history = client.get_price_history(
    token_id="your_token_id",
    interval="1h",
    startTs=start_timestamp,
    endTs=end_timestamp
)

# Backtest your strategy on historical data
```

## Resources

- [Polymarket Documentation](https://docs.polymarket.com/)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
- [Gamma API Reference](https://docs.polymarket.com/developers/gamma-markets-api/)
- [CLOB API Reference](https://docs.polymarket.com/developers/CLOB/introduction)

## Disclaimer

This bot is for educational purposes. Trading involves risk, and you should never trade with money you can't afford to lose. Always:
- Test thoroughly before live trading
- Understand the markets you're trading
- Comply with local regulations
- Use proper risk management

## License

MIT License - feel free to modify and use as needed.

## Support

For issues with:
- The bot code: Create an issue in this repository
- Polymarket API: Contact support@polymarket.com
- py-clob-client: Visit the [official GitHub](https://github.com/Polymarket/py-clob-client)
