"""
Polymarket Trading Bot
A basic framework for automated trading on Polymarket
"""

import os
import time
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PolymarketBot:
    """
    A basic trading bot for Polymarket
    """
    
    def __init__(self, private_key: str, signature_type: int = 0, funder: Optional[str] = None):
        """
        Initialize the Polymarket bot
        
        Args:
            private_key: Your wallet's private key
            signature_type: 0 for EOA, 1 for Magic wallet, 2 for Gnosis Safe
            funder: Funder address (required for signature_type 1 or 2)
        """
        self.host = "https://clob.polymarket.com"
        self.chain_id = 137  # Polygon mainnet
        
        # Initialize CLOB client
        if signature_type in [1, 2] and not funder:
            raise ValueError("Funder address required for signature_type 1 or 2")
        
        client_params = {
            "host": self.host,
            "key": private_key,
            "chain_id": self.chain_id,
            "signature_type": signature_type
        }
        
        if funder:
            client_params["funder"] = funder
        
        self.client = ClobClient(**client_params)
        
        # Set API credentials
        self.client.set_api_creds(self.client.create_or_derive_api_creds())
        
        logger.info("Polymarket bot initialized successfully")
    
    def get_market_data(self, token_id: str) -> Dict:
        """
        Get current market data for a token
        
        Args:
            token_id: The token ID to query
            
        Returns:
            Dictionary with market data
        """
        try:
            midpoint = self.client.get_midpoint(token_id)
            buy_price = self.client.get_price(token_id, side="BUY")
            sell_price = self.client.get_price(token_id, side="SELL")
            order_book = self.client.get_order_book(token_id)
            last_trade = self.client.get_last_trade_price(token_id)
            
            return {
                "token_id": token_id,
                "midpoint": midpoint,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "spread": sell_price - buy_price if buy_price and sell_price else None,
                "last_trade": last_trade,
                "order_book": order_book
            }
        except Exception as e:
            logger.error(f"Error fetching market data for {token_id}: {e}")
            return {}
    
    def place_market_order(
        self, 
        token_id: str, 
        amount: float, 
        side: str,
        order_type: OrderType = OrderType.FOK
    ) -> Optional[Dict]:
        """
        Place a market order
        
        Args:
            token_id: The token ID to trade
            amount: Amount in USDC
            side: BUY or SELL
            order_type: FOK (Fill or Kill) or GTC (Good til Cancel)
            
        Returns:
            Order response or None if failed
        """
        try:
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=side,
                order_type=order_type
            )
            
            signed_order = self.client.create_market_order(order_args)
            response = self.client.post_order(signed_order, order_type)
            
            logger.info(f"Order placed: {side} {amount} USDC of {token_id}")
            return response
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def check_arbitrage_opportunity(self, yes_token_id: str, no_token_id: str) -> Optional[Dict]:
        """
        Check for arbitrage opportunities between YES and NO tokens
        Since YES + NO = $1.00 at settlement, if we can buy both for < $1.00, it's arbitrage
        
        Args:
            yes_token_id: YES token ID
            no_token_id: NO token ID
            
        Returns:
            Arbitrage data if opportunity exists, None otherwise
        """
        try:
            yes_price = self.client.get_price(yes_token_id, side="BUY")
            no_price = self.client.get_price(no_token_id, side="BUY")
            
            if yes_price and no_price:
                combined_cost = yes_price + no_price
                profit = 1.00 - combined_cost
                profit_pct = (profit / combined_cost) * 100 if combined_cost > 0 else 0
                
                if profit > 0:
                    logger.info(f"Arbitrage opportunity found! Profit: ${profit:.4f} ({profit_pct:.2f}%)")
                    return {
                        "yes_token": yes_token_id,
                        "no_token": no_token_id,
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "combined_cost": combined_cost,
                        "profit": profit,
                        "profit_pct": profit_pct
                    }
        except Exception as e:
            logger.error(f"Error checking arbitrage: {e}")
        
        return None
    
    def execute_arbitrage(self, arb_data: Dict, amount: float) -> bool:
        """
        Execute an arbitrage trade
        
        Args:
            arb_data: Arbitrage opportunity data
            amount: Amount in USDC to invest
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate how much to buy of each token
            yes_amount = amount * (arb_data["yes_price"] / arb_data["combined_cost"])
            no_amount = amount * (arb_data["no_price"] / arb_data["combined_cost"])
            
            # Place both orders
            yes_order = self.place_market_order(arb_data["yes_token"], yes_amount, BUY)
            no_order = self.place_market_order(arb_data["no_token"], no_amount, BUY)
            
            if yes_order and no_order:
                logger.info(f"Arbitrage executed successfully! Expected profit: ${arb_data['profit'] * amount:.2f}")
                return True
            else:
                logger.error("Failed to execute complete arbitrage - one or both orders failed")
                return False
        except Exception as e:
            logger.error(f"Error executing arbitrage: {e}")
            return False
    
    def simple_momentum_strategy(self, token_id: str, lookback_trades: int = 10) -> Optional[str]:
        """
        Simple momentum strategy based on recent trades
        
        Args:
            token_id: Token to analyze
            lookback_trades: Number of recent trades to analyze
            
        Returns:
            "BUY", "SELL", or None
        """
        try:
            # Get recent trades
            trades = self.client.get_trades()
            
            if len(trades) < lookback_trades:
                return None
            
            recent_trades = trades[:lookback_trades]
            
            # Calculate price momentum
            prices = [float(trade.get('price', 0)) for trade in recent_trades]
            avg_price = sum(prices) / len(prices)
            current_price = self.client.get_last_trade_price(token_id)
            
            if current_price > avg_price * 1.02:  # 2% above average
                return SELL
            elif current_price < avg_price * 0.98:  # 2% below average
                return BUY
            
            return None
        except Exception as e:
            logger.error(f"Error in momentum strategy: {e}")
            return None
    
    def get_balance(self) -> float:
        """
        Get current USDC balance (simplified)
        Note: This requires additional implementation based on your wallet type
        """
        # This is a placeholder - actual implementation depends on wallet integration
        logger.warning("Balance checking not fully implemented")
        return 0.0
    
    def run_monitoring_loop(self, token_ids: List[str], interval: int = 60):
        """
        Run a continuous monitoring loop
        
        Args:
            token_ids: List of token IDs to monitor
            interval: Seconds between checks
        """
        logger.info(f"Starting monitoring loop for {len(token_ids)} tokens")
        
        while True:
            try:
                for token_id in token_ids:
                    market_data = self.get_market_data(token_id)
                    logger.info(f"Token {token_id}: Mid={market_data.get('midpoint')}, Spread={market_data.get('spread')}")
                
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Monitoring loop stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval)


def main():
    """
    Main entry point for the bot
    """
    # Load environment variables
    load_dotenv()
    
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        raise ValueError("POLYMARKET_PRIVATE_KEY not found in environment variables")
    
    # For Magic/email wallets, also set POLYMARKET_FUNDER
    signature_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "0"))
    funder = os.getenv("POLYMARKET_FUNDER")
    
    # Initialize bot
    bot = PolymarketBot(
        private_key=private_key,
        signature_type=signature_type,
        funder=funder
    )
    
    # Example: Monitor specific markets
    token_ids = [
        # Add your token IDs here
        # You can get these from the Gamma API: https://docs.polymarket.com/
    ]
    
    if token_ids:
        bot.run_monitoring_loop(token_ids, interval=30)
    else:
        logger.info("No token IDs specified. Add token IDs to start monitoring.")


if __name__ == "__main__":
    main()
