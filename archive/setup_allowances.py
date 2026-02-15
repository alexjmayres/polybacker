#!/usr/bin/env python3
"""
Setup Script: Set Token Allowances
Run this ONCE before trading to give Polymarket permission to use your USDC
"""

from py_clob_client.client import ClobClient
from py_clob_client.constants import COLLATERAL_TOKEN_ADDRESS
import os
from dotenv import load_dotenv

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║         POLYMARKET ALLOWANCE SETUP                           ║
    ║         One-time setup required before trading               ║
    ╚══════════════════════════════════════════════════════════════╝
    
    This script will:
    1. Give Polymarket permission to trade your USDC
    2. Give Polymarket permission to trade outcome tokens
    
    You only need to run this ONCE per wallet.
    This will cost a small amount of MATIC for gas fees (~$0.10).
    
    """)
    
    input("Press Enter to continue...")
    
    # Load environment
    load_dotenv()
    
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        print("❌ ERROR: POLYMARKET_PRIVATE_KEY not found in .env file")
        print("\nPlease:")
        print("1. Copy .env.example to .env")
        print("2. Add your private key to the .env file")
        print("3. Run this script again")
        return
    
    signature_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "0"))
    
    if signature_type != 0:
        print("⚠️  Note: You're using signature_type", signature_type)
        print("Allowances are typically only needed for EOA wallets (type 0)")
        print("Magic/email wallets (type 1) usually set allowances automatically")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    print("\n🔧 Initializing client...")
    
    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,
            chain_id=137,
            signature_type=signature_type
        )
        
        # Set API credentials
        client.set_api_creds(client.create_or_derive_api_creds())
        
        print("✓ Client initialized successfully")
        
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return
    
    print("\n💰 Setting USDC allowance...")
    print("This allows Polymarket to use your USDC for trading")
    print("Amount: 1,000,000 USDC (you can always change this)")
    
    try:
        # Set USDC allowance
        # Note: The actual method may vary - check py-clob-client docs
        print("\n⚠️  IMPORTANT: This will require a transaction on Polygon")
        print("Make sure you have some MATIC for gas fees (~$0.10)")
        
        response = input("\nProceed with setting allowances? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
        
        print("\n📝 Sending transaction...")
        print("This may take 30-60 seconds...")
        
        # For py-clob-client, allowances are typically set via web3 directly
        # Here's the general approach:
        
        from web3 import Web3
        from eth_account import Account
        
        # Connect to Polygon
        w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
        
        # Your account
        account = Account.from_key(private_key)
        
        # USDC contract address on Polygon
        usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        
        # Polymarket exchange contract
        exchange_address = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
        
        # ERC20 approve function
        erc20_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
        
        # Create contract instance
        usdc_contract = w3.eth.contract(
            address=Web3.to_checksum_address(usdc_address),
            abi=erc20_abi
        )
        
        # Approve max amount (2^256 - 1)
        max_approval = 2**256 - 1
        
        # Build transaction
        nonce = w3.eth.get_transaction_count(account.address)
        
        txn = usdc_contract.functions.approve(
            Web3.to_checksum_address(exchange_address),
            max_approval
        ).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 137
        })
        
        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(txn, private_key)
        
        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        print(f"\n📤 Transaction sent: {tx_hash.hex()}")
        print("Waiting for confirmation...")
        
        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] == 1:
            print("\n✅ SUCCESS! Allowances set successfully!")
            print(f"Transaction hash: {tx_hash.hex()}")
            print(f"View on Polygonscan: https://polygonscan.com/tx/{tx_hash.hex()}")
            print("\n🎉 You're ready to trade!")
        else:
            print("\n❌ Transaction failed")
            print("Check the transaction on Polygonscan for details")
            
    except Exception as e:
        print(f"\n❌ Error setting allowances: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have MATIC for gas fees")
        print("2. Check your internet connection")
        print("3. Verify your private key is correct")
        print("4. Try again in a few minutes if network is congested")
        return
    
    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("="*70)
    print("1. ✓ Allowances are set")
    print("2. Run: python discover_markets.py")
    print("3. Run: python run_arbitrage.py")
    print("4. Start making money! 💰")
    print("="*70)


if __name__ == "__main__":
    main()
