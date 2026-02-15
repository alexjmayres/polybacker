#!/usr/bin/env python3
"""
Polymarket Arbitrage Bot - Automated Money Making
Finds and executes risk-free arbitrage opportunities
"""

from polymarket_bot import PolymarketBot
import os
from dotenv import load_dotenv
import time
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arbitrage_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
MIN_PROFIT_PCT = float(os.getenv("MIN_PROFIT_THRESHOLD", "1.0"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "10.0"))
MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "100.0"))
CHECK_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))

# Track statistics
stats = {
    "trades_executed": 0,
    "total_profit": 0.0,
    "opportunities_found": 0,
    "start_time": datetime.now(),
    "failed_trades": 0
}


def load_markets():
    """Load market token IDs from JSON file"""
    try:
        with open('token_ids.json', 'r') as f:
            markets = json.load(f)
            logger.info(f"Loaded {len(markets)} markets from token_ids.json")
            return markets
    except FileNotFoundError:
        logger.warning("token_ids.json not found. Run discover_markets.py first!")
        logger.info("Attempting to fetch markets directly from API...")
        
        # Fallback: fetch directly from API
        import requests
        try:
            response = requests.get("https://gamma-api.polymarket.com/markets?limit=50&active=true")
            markets = response.json()
            
            # Save for future use
            with open('token_ids.json', 'w') as f:
                json.dump(markets, f, indent=2)
            
            logger.info(f"Fetched {len(markets)} markets from API")
            return markets
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []


def save_trade_record(trade_data: dict):
    """Save trade details to file"""
    try:
        with open('trades.jsonl', 'a') as f:
            f.write(json.dumps(trade_data) + '\n')
    except Exception as e:
        logger.error(f"Failed to save trade record: {e}")


def print_stats():
    """Print current statistics"""
    runtime = datetime.now() - stats['start_time']
    hours = runtime.total_seconds() / 3600
    
    print("\n" + "="*70)
    print("📊 BOT STATISTICS")
    print("="*70)
    print(f"Runtime: {runtime}")
    print(f"Opportunities found: {stats['opportunities_found']}")
    print(f"Trades executed: {stats['trades_executed']}")
    print(f"Failed trades: {stats['failed_trades']}")
    print(f"Total profit: ${stats['total_profit']:.2f}")
    if hours > 0:
        print(f"Profit per hour: ${stats['total_profit']/hours:.2f}")
    if stats['trades_executed'] > 0:
        print(f"Average profit per trade: ${stats['total_profit']/stats['trades_executed']:.2f}")
    print("="*70 + "\n")


def main():
    """Main bot loop"""
    
    # Initialize bot
    logger.info("Initializing Polymarket Arbitrage Bot...")
    
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        logger.error("POLYMARKET_PRIVATE_KEY not found in .env file!")
        logger.error("Copy .env.example to .env and fill in your private key")
        return
    
    signature_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "0"))
    funder = os.getenv("POLYMARKET_FUNDER")
    
    try:
        bot = PolymarketBot(
            private_key=private_key,
            signature_type=signature_type,
            funder=funder
        )
        logger.info("✓ Bot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        return
    
    # Load markets
    markets = load_markets()
    if not markets:
        logger.error("No markets available. Exiting.")
        return
    
    # Filter markets with valid token pairs
    valid_markets = []
    for market in markets:
        tokens = market.get('tokens', [])
        if len(tokens) >= 2:
            valid_markets.append(market)
    
    logger.info(f"Monitoring {len(valid_markets)} markets for arbitrage")
    logger.info(f"Min profit threshold: {MIN_PROFIT_PCT}%")
    logger.info(f"Trade amount: ${TRADE_AMOUNT}")
    logger.info(f"Check interval: {CHECK_INTERVAL}s")
    logger.info(f"\nBot is running... Press Ctrl+C to stop\n")
    
    # Main loop
    iteration = 0
    while True:
        try:
            iteration += 1
            logger.info(f"--- Iteration {iteration} ---")
            
            # Check each market
            for i, market in enumerate(valid_markets, 1):
                try:
                    tokens = market['tokens']
                    yes_token = tokens[0]['token_id']
                    no_token = tokens[1]['token_id']
                    
                    # Check for arbitrage
                    arb = bot.check_arbitrage_opportunity(yes_token, no_token)
                    
                    if arb and arb['profit_pct'] >= MIN_PROFIT_PCT:
                        stats['opportunities_found'] += 1
                        
                        logger.info("\n" + "🎯"*25)
                        logger.info(f"ARBITRAGE OPPORTUNITY #{stats['opportunities_found']}")
                        logger.info("🎯"*25)
                        logger.info(f"Market: {market.get('question', 'Unknown')}")
                        logger.info(f"YES price: ${arb['yes_price']:.4f}")
                        logger.info(f"NO price: ${arb['no_price']:.4f}")
                        logger.info(f"Combined cost: ${arb['combined_cost']:.4f}")
                        logger.info(f"Guaranteed payout: $1.00")
                        logger.info(f"Profit: ${arb['profit']:.4f} ({arb['profit_pct']:.2f}%)")
                        
                        # Calculate trade amount (don't exceed max position size)
                        trade_amt = min(TRADE_AMOUNT, MAX_POSITION_SIZE)
                        expected_profit = arb['profit'] * trade_amt
                        
                        logger.info(f"\nExecuting ${trade_amt} trade...")
                        logger.info(f"Expected profit: ${expected_profit:.2f}")
                        
                        # Execute the trade
                        success = bot.execute_arbitrage(arb, trade_amt)
                        
                        if success:
                            stats['trades_executed'] += 1
                            stats['total_profit'] += expected_profit
                            
                            logger.info(f"✓ TRADE EXECUTED SUCCESSFULLY!")
                            logger.info(f"Total trades: {stats['trades_executed']}")
                            logger.info(f"Total profit: ${stats['total_profit']:.2f}")
                            
                            # Save trade record
                            trade_record = {
                                "timestamp": datetime.now().isoformat(),
                                "market": market.get('question'),
                                "yes_token": yes_token,
                                "no_token": no_token,
                                "yes_price": arb['yes_price'],
                                "no_price": arb['no_price'],
                                "amount": trade_amt,
                                "profit": expected_profit,
                                "profit_pct": arb['profit_pct']
                            }
                            save_trade_record(trade_record)
                        else:
                            stats['failed_trades'] += 1
                            logger.warning(f"✗ Trade failed")
                        
                        logger.info("🎯"*25 + "\n")
                    
                except Exception as e:
                    logger.error(f"Error checking market {i}: {e}")
                    continue
            
            # Print stats every 10 iterations
            if iteration % 10 == 0:
                print_stats()
            
            # Wait before next check
            logger.info(f"Checked {len(valid_markets)} markets. Waiting {CHECK_INTERVAL}s...\n")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("\n\n🛑 Bot stopped by user")
            print_stats()
            
            # Print trade history
            try:
                with open('trades.jsonl', 'r') as f:
                    trades = [json.loads(line) for line in f]
                    if trades:
                        print("\n📋 TRADE HISTORY:")
                        print("="*70)
                        for i, trade in enumerate(trades, 1):
                            print(f"{i}. {trade['timestamp']}")
                            print(f"   {trade['market']}")
                            print(f"   Profit: ${trade['profit']:.2f} ({trade['profit_pct']:.2f}%)")
                            print()
            except FileNotFoundError:
                pass
            
            break
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.info(f"Continuing in {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║         POLYMARKET ARBITRAGE BOT v1.0                        ║
    ║         Automated Risk-Free Profit Finder                    ║
    ╚══════════════════════════════════════════════════════════════╝
    
    This bot will:
    ✓ Monitor prediction markets 24/7
    ✓ Detect arbitrage opportunities (YES + NO < $1.00)
    ✓ Execute risk-free trades automatically
    ✓ Track profits and statistics
    
    Make sure you have:
    ✓ USDC in your Polygon wallet
    ✓ Token allowances set (run setup_allowances.py)
    ✓ Markets discovered (run discover_markets.py)
    
    """)
    
    input("Press Enter to start the bot...")
    main()
