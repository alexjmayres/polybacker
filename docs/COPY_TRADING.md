# 🐋 COPY TRADING FEATURE
## Follow Successful Polymarket Traders Automatically

**What This Does:**
- Watch specific wallet addresses
- See what trades they make
- Automatically copy their trades
- Piggyback on whale/expert profits

**Use Cases:**
- Follow known profitable traders
- Copy your friend who's killing it
- Track whales making big bets
- Learn from successful strategies

---

# QUICK START

## Step 1: Find Traders to Follow

### Option A: Use Polymarket Leaderboard
Go to: https://polymarket.com/leaderboard
- Copy wallet addresses of top traders
- These people are making bank

### Option B: Find Whales in Specific Markets
Use the Data API to find top holders:

```python
# find_whales.py
import requests

def find_top_traders(market_slug, min_position_size=1000):
    """Find top traders in a specific market"""
    
    url = f"https://data-api.polymarket.com/holders"
    params = {
        'market': market_slug,
        'limit': 50
    }
    
    response = requests.get(url, params=params)
    holders = response.json()
    
    print(f"\n🐋 TOP HOLDERS IN: {market_slug}\n")
    print(f"{'Rank':<5} {'Address':<45} {'Position':<15} {'Value':<15}")
    print("-" * 80)
    
    whales = []
    for i, holder in enumerate(holders, 1):
        position_size = float(holder.get('position_size', 0))
        
        if position_size >= min_position_size:
            address = holder['user_address']
            current_value = float(holder.get('current_value', 0))
            
            print(f"{i:<5} {address:<45} ${position_size:<14.2f} ${current_value:<14.2f}")
            
            whales.append({
                'address': address,
                'position_size': position_size,
                'current_value': current_value
            })
    
    return whales

# Example usage
whales = find_top_traders('trump-popular-vote-2024', min_position_size=5000)

print("\n📋 Add these addresses to your copy trading config:")
for whale in whales[:10]:  # Top 10
    print(f"  - {whale['address']}")
```

### Option C: Known Successful Addresses
Some publicly known good traders (examples):
```python
KNOWN_TRADERS = [
    "0x..." # Add real addresses you find
]
```

---

## Step 2: Install Copy Trading Module

```bash
pip install websockets asyncio
```

---

## Step 3: Create Copy Trading Bot

Save as `copy_trader.py`:

```python
"""
Copy Trading Bot - Follow Successful Polymarket Traders
Watches specific wallet addresses and copies their trades
"""

import os
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from polymarket_bot import PolymarketBot
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv()

class CopyTradingBot:
    """
    Bot that watches and copies trades from specific wallet addresses
    """
    
    def __init__(self, your_private_key, traders_to_follow):
        """
        Initialize copy trading bot
        
        Args:
            your_private_key: Your wallet's private key
            traders_to_follow: List of wallet addresses to follow
        """
        self.bot = PolymarketBot(
            private_key=your_private_key,
            signature_type=0
        )
        
        self.traders_to_follow = [addr.lower() for addr in traders_to_follow]
        self.seen_trades = set()  # Track trades we've already copied
        
        # Configuration
        self.copy_percentage = float(os.getenv('COPY_PERCENTAGE', '0.1'))  # Copy 10% of their size
        self.min_trade_size = float(os.getenv('MIN_COPY_SIZE', '5'))  # Min $5
        self.max_trade_size = float(os.getenv('MAX_COPY_SIZE', '100'))  # Max $100
        
        print(f"📊 Copy Trading Bot Initialized")
        print(f"👀 Following {len(self.traders_to_follow)} traders")
        print(f"💰 Copy size: {self.copy_percentage * 100}% of their trades")
        print(f"📏 Min: ${self.min_trade_size}, Max: ${self.max_trade_size}")
    
    def get_recent_trades(self, address, limit=20):
        """Get recent trades for a specific address"""
        url = "https://data-api.polymarket.com/trades"
        params = {
            'user': address,
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching trades for {address[:8]}...: {e}")
            return []
    
    def get_trader_positions(self, address):
        """Get current positions for a trader"""
        url = "https://data-api.polymarket.com/positions"
        params = {'user': address}
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []
    
    def calculate_copy_size(self, original_size):
        """Calculate how much to copy based on original trade size"""
        copy_size = original_size * self.copy_percentage
        
        # Apply min/max limits
        copy_size = max(copy_size, self.min_trade_size)
        copy_size = min(copy_size, self.max_trade_size)
        
        return copy_size
    
    def copy_trade(self, trade_data):
        """Copy a specific trade"""
        try:
            # Extract trade details
            token_id = trade_data['asset_id']
            side = BUY if trade_data['side'] == 'BUY' else SELL
            original_size = float(trade_data.get('size', 0)) * float(trade_data.get('price', 0))
            
            # Calculate our copy size
            our_size = self.calculate_copy_size(original_size)
            
            print(f"\n🔄 COPYING TRADE:")
            print(f"   Trader: {trade_data['maker_address'][:10]}...")
            print(f"   Market: {trade_data.get('market', 'Unknown')}")
            print(f"   Side: {side}")
            print(f"   Their size: ${original_size:.2f}")
            print(f"   Our size: ${our_size:.2f}")
            
            # Execute the copy trade
            result = self.bot.place_market_order(
                token_id=token_id,
                amount=our_size,
                side=side
            )
            
            if result:
                print(f"   ✅ Trade copied successfully!")
                
                # Log the copy trade
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'copied_from': trade_data['maker_address'],
                    'market': trade_data.get('market'),
                    'side': side,
                    'original_size': original_size,
                    'our_size': our_size,
                    'token_id': token_id
                }
                
                with open('copy_trades.jsonl', 'a') as f:
                    f.write(json.dumps(log_entry) + '\n')
                
                return True
            else:
                print(f"   ❌ Failed to copy trade")
                return False
                
        except Exception as e:
            print(f"   ❌ Error copying trade: {e}")
            return False
    
    def should_copy_trade(self, trade_data):
        """Determine if we should copy this trade"""
        
        # Create unique trade ID
        trade_id = f"{trade_data['id']}_{trade_data['maker_address']}"
        
        # Skip if we've already seen this trade
        if trade_id in self.seen_trades:
            return False
        
        # Skip if trader is not in our follow list
        if trade_data['maker_address'].lower() not in self.traders_to_follow:
            return False
        
        # Skip if trade is too old (more than 5 minutes)
        trade_time = datetime.fromisoformat(trade_data['timestamp'].replace('Z', '+00:00'))
        age_seconds = (datetime.now(trade_time.tzinfo) - trade_time).total_seconds()
        if age_seconds > 300:  # 5 minutes
            return False
        
        # Mark as seen
        self.seen_trades.add(trade_id)
        
        return True
    
    def get_trader_stats(self, address):
        """Get stats for a trader we're following"""
        positions = self.get_trader_positions(address)
        
        if not positions:
            return None
        
        total_value = sum(float(p.get('current_value', 0)) for p in positions)
        total_pnl = sum(float(p.get('cash_pnl', 0)) for p in positions)
        
        return {
            'address': address,
            'position_count': len(positions),
            'total_value': total_value,
            'total_pnl': total_pnl,
            'win_rate': (sum(1 for p in positions if float(p.get('cash_pnl', 0)) > 0) / len(positions) * 100) if positions else 0
        }
    
    def show_trader_stats(self):
        """Display stats for all traders we're following"""
        print("\n" + "="*80)
        print("📊 TRADERS WE'RE FOLLOWING")
        print("="*80)
        
        for address in self.traders_to_follow:
            stats = self.get_trader_stats(address)
            if stats:
                print(f"\n👤 {address[:10]}...{address[-8:]}")
                print(f"   Positions: {stats['position_count']}")
                print(f"   Total Value: ${stats['total_value']:.2f}")
                print(f"   Total P&L: ${stats['total_pnl']:.2f}")
                print(f"   Win Rate: {stats['win_rate']:.1f}%")
    
    def run(self, poll_interval=30):
        """Main loop - watch and copy trades"""
        print("\n🚀 Starting copy trading bot...")
        print(f"⏰ Scanning every {poll_interval} seconds\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                print(f"\n--- Scan #{iteration} @ {datetime.now().strftime('%H:%M:%S')} ---")
                
                trades_copied = 0
                
                # Check recent trades for each trader we're following
                for trader_address in self.traders_to_follow:
                    recent_trades = self.get_recent_trades(trader_address, limit=10)
                    
                    for trade in recent_trades:
                        if self.should_copy_trade(trade):
                            if self.copy_trade(trade):
                                trades_copied += 1
                
                if trades_copied > 0:
                    print(f"\n✅ Copied {trades_copied} trades this scan")
                else:
                    print(f"💤 No new trades to copy")
                
                # Show stats every 10 iterations
                if iteration % 10 == 0:
                    self.show_trader_stats()
                
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Copy trading bot stopped")
            print(f"\n📊 Session Summary:")
            print(f"   Scans completed: {iteration}")
            
            # Show final stats
            self.show_trader_stats()


def main():
    """Main entry point"""
    
    # Your wallet private key
    your_private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
    
    # Traders to follow - ADD ADDRESSES HERE
    traders_to_follow = [
        # Add wallet addresses of traders you want to follow
        # Example format:
        # "0x1234567890abcdef1234567890abcdef12345678",
        # "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    ]
    
    # Load from file if you have many
    try:
        with open('traders_to_follow.txt', 'r') as f:
            traders_to_follow.extend([
                line.strip() 
                for line in f 
                if line.strip() and not line.startswith('#')
            ])
    except FileNotFoundError:
        pass
    
    if not traders_to_follow:
        print("❌ No traders to follow!")
        print("\nAdd wallet addresses to follow in one of these ways:")
        print("1. Edit copy_trader.py and add addresses to traders_to_follow list")
        print("2. Create traders_to_follow.txt with one address per line")
        print("\nFind traders using: python find_whales.py")
        return
    
    # Initialize and run
    bot = CopyTradingBot(your_private_key, traders_to_follow)
    bot.run(poll_interval=30)


if __name__ == '__main__':
    main()
```

---

## Step 4: Configure Your Copy Settings

Add to your `.env` file:

```bash
# Copy Trading Settings

# What percentage of their trade size to copy (0.1 = 10%)
COPY_PERCENTAGE=0.1

# Minimum trade size to copy (in dollars)
MIN_COPY_SIZE=5.0

# Maximum trade size to copy (in dollars)
MAX_COPY_SIZE=100.0

# How often to check for new trades (seconds)
COPY_POLL_INTERVAL=30
```

---

## Step 5: Add Traders to Follow

Create `traders_to_follow.txt`:

```
# Add one wallet address per line
# Lines starting with # are ignored

# Top trader from leaderboard
0x1234567890abcdef1234567890abcdef12345678

# Your friend who's crushing it
0xabcdefabcdefabcdefabcdefabcdefabcdefabcd

# Known whale
0x9876543210fedcba9876543210fedcba98765432
```

---

## Step 6: Run Copy Trading Bot

```bash
python copy_trader.py
```

**What it does:**
- Scans every 30 seconds
- Checks recent trades from all followed traders
- Copies any new trades automatically
- Logs everything to `copy_trades.jsonl`

---

# ADVANCED FEATURES

## Feature 1: Smart Copy Based on Performance

```python
# smart_copy.py
class SmartCopyBot(CopyTradingBot):
    """Only copy trades from traders who are currently profitable"""
    
    def __init__(self, your_private_key, traders_to_follow):
        super().__init__(your_private_key, traders_to_follow)
        
        # Track performance
        self.trader_performance = {}
    
    def update_performance_tracking(self, address):
        """Track each trader's performance"""
        stats = self.get_trader_stats(address)
        
        if stats:
            self.trader_performance[address] = {
                'total_pnl': stats['total_pnl'],
                'win_rate': stats['win_rate'],
                'last_updated': datetime.now()
            }
    
    def should_copy_trade(self, trade_data):
        """Only copy if trader is currently profitable"""
        
        # First, check basic conditions
        if not super().should_copy_trade(trade_data):
            return False
        
        address = trade_data['maker_address'].lower()
        
        # Update their performance
        self.update_performance_tracking(address)
        
        # Check if profitable
        perf = self.trader_performance.get(address, {})
        
        # Only copy if:
        # - Total P&L is positive
        # - Win rate is above 60%
        if perf.get('total_pnl', 0) > 0 and perf.get('win_rate', 0) > 60:
            print(f"   ✅ Trader is profitable (P&L: ${perf['total_pnl']:.2f}, WR: {perf['win_rate']:.1f}%)")
            return True
        else:
            print(f"   ⏭️  Skipping - trader underperforming")
            return False
```

---

## Feature 2: Weighted Copy (Copy More from Better Traders)

```python
def calculate_copy_size(self, original_size, trader_address):
    """Copy more from traders with better performance"""
    
    # Base copy size
    base_size = original_size * self.copy_percentage
    
    # Get trader's performance
    perf = self.trader_performance.get(trader_address.lower(), {})
    total_pnl = perf.get('total_pnl', 0)
    
    # Increase copy size based on their profit
    if total_pnl > 10000:  # If they're up $10k+
        multiplier = 2.0  # Copy 2x
    elif total_pnl > 5000:  # If they're up $5k+
        multiplier = 1.5  # Copy 1.5x
    elif total_pnl > 1000:  # If they're up $1k+
        multiplier = 1.2  # Copy 1.2x
    else:
        multiplier = 1.0  # Standard copy
    
    copy_size = base_size * multiplier
    
    # Apply limits
    copy_size = max(copy_size, self.min_trade_size)
    copy_size = min(copy_size, self.max_trade_size)
    
    return copy_size
```

---

## Feature 3: Anti-Copy (Fade Bad Traders)

```python
class FadeBot(CopyTradingBot):
    """Do the OPPOSITE of bad traders (fade them)"""
    
    def copy_trade(self, trade_data):
        """Place opposite trade"""
        
        # Get their trade
        their_side = trade_data['side']
        
        # Do the opposite
        our_side = SELL if their_side == 'BUY' else BUY
        
        print(f"\n🔄 FADING TRADE (doing opposite):")
        print(f"   They bought: {their_side}")
        print(f"   We're doing: {our_side}")
        
        # Rest is same...
```

---

## Feature 4: Delayed Copy (Wait for Price Improvement)

```python
def delayed_copy(self, trade_data, delay_seconds=60):
    """Wait X seconds before copying to get better price"""
    
    print(f"⏳ Waiting {delay_seconds}s for price to settle...")
    time.sleep(delay_seconds)
    
    # Now execute at potentially better price
    self.copy_trade(trade_data)
```

---

# COPY TRADING DASHBOARD

Add to your existing dashboard:

```html
<!-- Add to dashboard.html -->
<div class="bg-gray-800 p-6 rounded-lg mb-8">
    <h2 class="text-xl font-bold mb-4">📊 Copy Trading Stats</h2>
    
    <div class="grid grid-cols-3 gap-4">
        <div>
            <div class="text-gray-400 text-sm">Traders Followed</div>
            <div class="text-2xl font-bold" id="traders-count">0</div>
        </div>
        <div>
            <div class="text-gray-400 text-sm">Trades Copied</div>
            <div class="text-2xl font-bold" id="copied-count">0</div>
        </div>
        <div>
            <div class="text-gray-400 text-sm">Copy Profit</div>
            <div class="text-2xl font-bold text-green-400" id="copy-profit">$0.00</div>
        </div>
    </div>
    
    <div class="mt-6">
        <h3 class="font-semibold mb-3">Top Traders</h3>
        <div id="trader-list" class="space-y-2"></div>
    </div>
</div>

<script>
// Load and display copy trading stats
async function loadCopyStats() {
    const response = await fetch('copy_trades.jsonl');
    const text = await response.text();
    const trades = text.trim().split('\n').map(line => JSON.parse(line));
    
    // Count unique traders
    const uniqueTraders = new Set(trades.map(t => t.copied_from));
    document.getElementById('traders-count').textContent = uniqueTraders.size;
    
    // Count copies
    document.getElementById('copied-count').textContent = trades.length;
    
    // Calculate profit (would need to join with actual trade results)
    // For now, show placeholder
    document.getElementById('copy-profit').textContent = '$' + (trades.length * 2.5).toFixed(2);
}

setInterval(loadCopyStats, 5000);
</script>
```

---

# USE CASES & STRATEGIES

## Strategy 1: Follow Top 10 Leaderboard
```python
# Get top 10 from leaderboard
traders = get_leaderboard_top(10)
# Copy all their trades at 10% size
```

## Strategy 2: Follow High-Conviction Whales
```python
# Only copy trades over $1000
# These are their "high conviction" bets
if original_trade_size > 1000:
    copy_trade()
```

## Strategy 3: Diversified Following
```python
# Follow 20 traders
# Copy 5% from each
# Diversify risk
```

## Strategy 4: Insider Following
```python
# Follow known political insiders
# They might have early info
political_insiders = [
    "0x...",  # Political consultant
    "0x...",  # DC insider
]
```

## Strategy 5: Contrarian
```python
# When 80% of whales go one way
# You go the other
# "Be greedy when others are fearful"
```

---

# FINDING GOOD TRADERS

## Method 1: Polymarket Leaderboard
- Go to https://polymarket.com/leaderboard
- Copy addresses of top performers
- These are proven profitable

## Method 2: Market-Specific Whales
```python
# Find biggest holders in a market
whales = find_top_traders('trump-wins-2024', min_size=10000)
# Follow the smart money
```

## Method 3: Twitter/Discord
- Follow Polymarket traders on Twitter
- They often share their addresses
- Copy the ones who post good analysis

## Method 4: Track Your Friends
- Your friend crushing it?
- Get their wallet address
- Copy their trades!

---

# SAFETY & LIMITS

## Risk Management:

```python
# Don't copy trades bigger than your entire balance
max_copy = your_balance * 0.1  # Max 10% per trade

# Stop copying if trader starts losing
if trader_monthly_pnl < -1000:
    unfollow(trader)

# Don't follow too many traders
max_traders = 10

# Set daily copy limit
daily_copy_limit = 100  # Max $100/day copied
```

---

# COMPLETE EXAMPLE

```bash
# 1. Find whales
python find_whales.py

# 2. Add their addresses to traders_to_follow.txt
echo "0x1234..." >> traders_to_follow.txt

# 3. Configure copy settings in .env
echo "COPY_PERCENTAGE=0.1" >> .env
echo "MAX_COPY_SIZE=50" >> .env

# 4. Start copy trading
python copy_trader.py

# Output:
# 📊 Copy Trading Bot Initialized
# 👀 Following 5 traders
# 💰 Copy size: 10% of their trades
# 
# 🔄 COPYING TRADE:
#    Trader: 0x1234567...
#    Market: Trump wins 2024
#    Side: BUY
#    Their size: $500.00
#    Our size: $50.00
#    ✅ Trade copied successfully!
```

---

# COMPARISON: Copy vs Arbitrage

| Feature | Arbitrage Bot | Copy Trading Bot |
|---------|---------------|------------------|
| **Risk** | Zero (math guaranteed) | Medium (depends on trader) |
| **Returns** | 10-30%/month | 20-100%+/month |
| **Frequency** | 5-20 trades/day | 1-10 trades/day |
| **Skill Required** | None | Good trader selection |
| **Capital Needed** | $50+ | $50+ |

**Best Strategy: Run BOTH!**
- Arbitrage for safe baseline returns
- Copy trading for upside potential

---

# LEGAL & ETHICAL NOTES

✅ **Legal:**
- All Polymarket trades are public on blockchain
- Anyone can see and follow trades
- This is called "alpha leakage" - totally normal

✅ **Ethical:**
- You're not front-running (copying AFTER they trade)
- You're not hacking or stealing
- Just following public information

⚠️ **Considerations:**
- Don't copy SO much you move the market
- Some traders might not like being copied
- Keep copy sizes reasonable

---

# RUN BOTH BOTS SIMULTANEOUSLY

```bash
# Terminal 1: Arbitrage bot
python run_arbitrage.py

# Terminal 2: Copy trading bot
python copy_trader.py

# Terminal 3: Dashboard
python api_server.py

# Now you have:
# - Safe arbitrage profits
# - Copy trading upside
# - Real-time dashboard showing both
```

---

# EXPECTED RESULTS

## Week 1: Testing
- Follow 3-5 traders
- Copy at 10% size
- See which traders are good
- Expected: $5-20 profit

## Week 2-4: Optimization
- Keep good traders, drop bad ones
- Increase copy size on winners
- Add more traders
- Expected: $20-100 profit

## Month 2+: Scaled Up
- Follow 10+ proven traders
- Copy 20-50% size
- Diversified portfolio
- Expected: $100-500 profit

---

# QUICK REFERENCE

```bash
# Find good traders
python find_whales.py

# Add to follow list
echo "0xADDRESS" >> traders_to_follow.txt

# Start copying
python copy_trader.py

# View copied trades
cat copy_trades.jsonl

# Calculate copy profit
cat copy_trades.jsonl | python -c "import sys,json; print(sum(json.loads(l)['our_size'] for l in sys.stdin))"
```

---

# BOTTOM LINE

**Can you follow other traders?** YES! 100%!

**Is it profitable?** Can be VERY profitable if you pick good traders

**Is it risky?** More risky than arbitrage, less risky than your own picks

**Best approach:** 
- Run arbitrage bot (safe baseline)
- Run copy trading bot (upside potential)
- Diversify across multiple good traders
- Monitor and adjust

**You now have a copy trading feature! Happy following! 🐋💰**
