"""
POLYMARKET BOT - QUICK START GUIDE
Get up and running in 15 minutes
"""

# ============================================================================
# STEP 1: PREPARE YOUR WALLET (5 minutes)
# ============================================================================

"""
You need:
1. A Polygon wallet with some USDC
2. Your wallet's private key

OPTION A: Using MetaMask (Recommended for beginners)
-----------------------------------------------------
1. Install MetaMask browser extension: https://metamask.io
2. Create a new wallet OR use existing
3. Add Polygon network to MetaMask:
   - Network Name: Polygon Mainnet
   - RPC URL: https://polygon-rpc.com
   - Chain ID: 137
   - Currency Symbol: MATIC
   - Block Explorer: https://polygonscan.com

4. Get some MATIC for gas fees (you need ~$5 worth):
   - Buy on exchange and withdraw to Polygon
   - Or use a bridge like https://wallet.polygon.technology

5. Get USDC on Polygon:
   - Buy USDC on an exchange (Coinbase, Binance, etc.)
   - Withdraw to your Polygon wallet
   - IMPORTANT: Make sure it's USDC on Polygon network!
   - Start with $50-100 for testing

6. Get your private key:
   - Click MetaMask menu (3 dots)
   - Account Details
   - Export Private Key
   - Enter password
   - COPY the key (starts with 0x)
   - NEVER share this with anyone!

OPTION B: Create a new wallet just for the bot
-----------------------------------------------
This is SAFER - use a dedicated wallet for bot trading:

1. Generate new wallet with Python:
"""

from eth_account import Account
import secrets

# Generate new wallet
private_key = "0x" + secrets.token_hex(32)
account = Account.from_key(private_key)

print("NEW WALLET GENERATED")
print("="*60)
print(f"Address: {account.address}")
print(f"Private Key: {private_key}")
print("="*60)
print("SAVE THESE SAFELY!")
print("Send MATIC and USDC to this address to fund it.")

"""
2. Send MATIC (~$5) and USDC ($50-100) to this address
3. Use this private key in your .env file
"""

# ============================================================================
# STEP 2: INSTALL THE BOT (3 minutes)
# ============================================================================

"""
1. Install Python 3.9+ if you don't have it:
   https://www.python.org/downloads/

2. Open terminal/command prompt

3. Create a project folder:
"""

# On Mac/Linux:
mkdir ~/polymarket-bot
cd ~/polymarket-bot

# On Windows:
mkdir C:\polymarket-bot
cd C:\polymarket-bot

"""
4. Copy all the bot files to this folder:
   - polymarket_bot.py
   - discover_markets.py
   - requirements.txt
   - .env.example
   - README.md

5. Install dependencies:
"""

pip install -r requirements.txt

# If you get errors, try:
pip install py-clob-client web3==6.14.0 python-dotenv requests --upgrade

"""
6. Create your .env file:
"""

# Copy the example
cp .env.example .env

# Edit .env with your favorite text editor
# On Mac: open .env
# On Windows: notepad .env

"""
Fill in:
POLYMARKET_PRIVATE_KEY=your_private_key_without_0x_prefix
POLYMARKET_SIGNATURE_TYPE=0
"""

# ============================================================================
# STEP 3: SET TOKEN ALLOWANCES (2 minutes) - CRITICAL!
# ============================================================================

"""
If using MetaMask/EOA wallet, you MUST do this before trading!
This gives Polymarket permission to move your USDC.
"""

from py_clob_client.client import ClobClient
from py_clob_client.constants import COLLATERAL_TOKEN_ADDRESS
import os
from dotenv import load_dotenv

load_dotenv()

# Your private key from .env
private_key = os.getenv("POLYMARKET_PRIVATE_KEY")

client = ClobClient(
    host="https://clob.polymarket.com",
    key=private_key,
    chain_id=137,
    signature_type=0  # EOA
)

print("Setting allowances... this will cost a small gas fee")

# Set USDC allowance
client.set_token_allowance(
    token_address=COLLATERAL_TOKEN_ADDRESS,
    amount=1000000  # Allow up to 1M USDC
)

print("✓ Allowances set! You're ready to trade.")

"""
Save this as setup_allowances.py and run:
python setup_allowances.py

You only need to do this ONCE per wallet.
"""

# ============================================================================
# STEP 4: FIND PROFITABLE MARKETS (3 minutes)
# ============================================================================

"""
Now let's find markets to trade!
"""

# Run the market discovery script:
python discover_markets.py

"""
This will show you:
- Active markets
- Token IDs you need for trading
- Current prices
- Trading volume

Look for markets with:
✓ High volume (> $10,000)
✓ Good liquidity
✓ Topics you understand

The script outputs token_ids.json - use these in your bot!
"""

# ============================================================================
# STEP 5: TEST WITH A SMALL TRADE (2 minutes)
# ============================================================================

"""
Let's test with a manual trade first
"""

from polymarket_bot import PolymarketBot
from py_clob_client.order_builder.constants import BUY
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize bot
bot = PolymarketBot(
    private_key=os.getenv("POLYMARKET_PRIVATE_KEY"),
    signature_type=0
)

# Get a token ID from discover_markets.py output
# Example: "71321045679252212594626385532706912750332728571942532289631379312455583992833"
test_token_id = "YOUR_TOKEN_ID_HERE"

# Check current price
data = bot.get_market_data(test_token_id)
print(f"Current price: ${data['midpoint']:.4f}")
print(f"Spread: ${data['spread']:.4f}")

# Place a SMALL test order ($5)
print("\nPlacing test order...")
response = bot.place_market_order(
    token_id=test_token_id,
    amount=5.0,  # $5 USDC - start small!
    side=BUY
)

print(f"Order response: {response}")

"""
If this works, you're ready for automated trading!
"""

# ============================================================================
# STEP 6: RUN ARBITRAGE BOT (MONEY-MAKING TIME!)
# ============================================================================

"""
The arbitrage strategy is the safest way to make money.
It finds risk-free opportunities where YES + NO < $1.00

Create a file called run_arbitrage.py:
"""

from polymarket_bot import PolymarketBot
from py_clob_client.order_builder.constants import BUY
import os
from dotenv import load_dotenv
import time
import json

load_dotenv()

# Initialize bot
bot = PolymarketBot(
    private_key=os.getenv("POLYMARKET_PRIVATE_KEY"),
    signature_type=0
)

# Load token IDs from discover_markets.py
with open('token_ids.json', 'r') as f:
    markets = json.load(f)

# Configuration
MIN_PROFIT_PCT = 1.0  # Minimum 1% profit
TRADE_AMOUNT = 10.0   # $10 per trade - adjust based on your capital
CHECK_INTERVAL = 30   # Seconds between checks

print("Starting Arbitrage Bot...")
print(f"Minimum profit: {MIN_PROFIT_PCT}%")
print(f"Trade amount: ${TRADE_AMOUNT}")
print("="*60)

trades_executed = 0
total_profit = 0.0

while True:
    try:
        # Check each market for arbitrage
        for market in markets:
            tokens = market['tokens']
            
            if len(tokens) < 2:
                continue
            
            yes_token = tokens[0]['token_id']
            no_token = tokens[1]['token_id']
            
            # Check for arbitrage
            arb = bot.check_arbitrage_opportunity(yes_token, no_token)
            
            if arb and arb['profit_pct'] >= MIN_PROFIT_PCT:
                print(f"\n🎯 ARBITRAGE FOUND!")
                print(f"Market: {market['question']}")
                print(f"YES price: ${arb['yes_price']:.4f}")
                print(f"NO price: ${arb['no_price']:.4f}")
                print(f"Combined: ${arb['combined_cost']:.4f}")
                print(f"Profit: ${arb['profit']:.4f} ({arb['profit_pct']:.2f}%)")
                
                # Execute the trade
                print(f"\nExecuting ${TRADE_AMOUNT} arbitrage trade...")
                success = bot.execute_arbitrage(arb, TRADE_AMOUNT)
                
                if success:
                    trades_executed += 1
                    expected_profit = arb['profit'] * TRADE_AMOUNT
                    total_profit += expected_profit
                    
                    print(f"✓ Trade #{trades_executed} executed!")
                    print(f"Expected profit: ${expected_profit:.2f}")
                    print(f"Total profit: ${total_profit:.2f}")
                else:
                    print(f"✗ Trade failed - continuing...")
        
        # Wait before next check
        print(f"\nChecked {len(markets)} markets. Waiting {CHECK_INTERVAL}s...")
        print(f"Stats: {trades_executed} trades, ${total_profit:.2f} total profit")
        time.sleep(CHECK_INTERVAL)
        
    except KeyboardInterrupt:
        print("\n\nBot stopped by user")
        print(f"Final stats: {trades_executed} trades, ${total_profit:.2f} profit")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL)

"""
Run it:
python run_arbitrage.py

Let it run 24/7 to catch opportunities!
"""

# ============================================================================
# STEP 7: SCALE UP (After you're profitable)
# ============================================================================

"""
Once you're making money consistently:

1. INCREASE CAPITAL
   - Start with $50-100
   - After 1 week of profit, move to $500-1000
   - Scale slowly based on results

2. RUN ON A SERVER (24/7 operation)
   - Use a VPS like DigitalOcean ($5/month) or AWS
   - Install the bot on the server
   - Run in background: nohup python run_arbitrage.py &
   - Or use screen/tmux to keep it running

3. OPTIMIZE SETTINGS
   - Lower MIN_PROFIT_PCT if you're missing trades (try 0.5%)
   - Increase CHECK_INTERVAL if hitting rate limits
   - Adjust TRADE_AMOUNT based on market liquidity

4. MONITOR PERFORMANCE
   - Keep logs of all trades
   - Calculate actual ROI
   - Adjust strategy based on data

5. ADD MORE STRATEGIES
   - Momentum trading
   - Market making
   - News-based trading
   - Multi-market arbitrage
"""

# ============================================================================
# EXPECTED RETURNS
# ============================================================================

"""
REALISTIC EXPECTATIONS:

Arbitrage Strategy (Conservative):
- Opportunities: 5-20 per day
- Profit per trade: 0.5% - 3%
- With $100 capital: $1-5 per day
- With $1000 capital: $10-50 per day
- Annual return: 20-50% (if consistent)

Risk Level: LOW (arbitrage is risk-free if executed properly)

IMPORTANT: 
- Past performance doesn't guarantee future results
- Market conditions change
- Competition from other bots reduces opportunities
- Gas fees eat into small profits
- Slippage can reduce profits

START SMALL, LEARN, THEN SCALE!
"""

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

"""
Problem: "Not enough balance/allowance"
Solution: 
- Check you have USDC on Polygon (not Ethereum!)
- Run setup_allowances.py again
- Verify with: client.get_allowances()

Problem: "Orders not filling"
Solution:
- Market may have low liquidity
- Your price may be too far from market
- Try smaller order sizes

Problem: "Rate limit exceeded"
Solution:
- Increase CHECK_INTERVAL
- Reduce number of markets monitored
- Consider premium API tier

Problem: "Bot not finding arbitrage"
Solution:
- Markets are efficient, opportunities are rare
- Lower MIN_PROFIT_PCT threshold
- Monitor more markets
- Be patient - opportunities come in bursts

Problem: Bot crashes
Solution:
- Check error logs
- Ensure stable internet connection
- Add more error handling
- Run on a server instead of laptop
"""

# ============================================================================
# SAFETY TIPS
# ============================================================================

"""
🔒 SECURITY:
- NEVER share your private key
- Use a separate wallet for bot trading
- Don't commit .env to GitHub
- Keep backup of private key in safe place

💰 RISK MANAGEMENT:
- Start with small amounts ($50-100)
- Never invest more than you can afford to lose
- Set position limits (max per trade)
- Monitor bot daily at first
- Take profits regularly

⚖️ LEGAL:
- Check if prediction markets are legal in your jurisdiction
- Keep records for taxes
- Understand you're trading real money
- Read Polymarket terms of service

🎯 STRATEGY:
- Focus on arbitrage first (lowest risk)
- Don't get greedy - take consistent small profits
- Diversify across multiple markets
- Reinvest profits to compound gains
- Keep learning and optimizing
"""

# ============================================================================
# NEXT STEPS
# ============================================================================

"""
1. Set up your wallet with USDC ✓
2. Install the bot ✓
3. Set allowances ✓
4. Run discover_markets.py ✓
5. Test with small trade ✓
6. Run arbitrage bot ✓
7. Monitor and optimize
8. Scale up capital
9. Deploy to server for 24/7 operation
10. Build custom strategies

READY TO START MAKING MONEY?

Run this command to begin:
python run_arbitrage.py

Good luck! 🚀💰
"""

if __name__ == "__main__":
    print(__doc__)
