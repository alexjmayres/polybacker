"""
Flask API Backend for Polymarket Bot Dashboard
Connects the Python trading bot with the React frontend
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import threading
import time
from datetime import datetime
from polymarket_bot import PolymarketBot
from py_clob_client.order_builder.constants import BUY
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global bot state
bot_state = {
    'status': 'stopped',
    'stats': {
        'total_profit': 0.0,
        'trades_executed': 0,
        'opportunities_found': 0,
        'failed_trades': 0,
        'start_time': None,
        'runtime': '0h 0m'
    },
    'config': {
        'min_profit': float(os.getenv('MIN_PROFIT_THRESHOLD', '1.0')),
        'trade_amount': float(os.getenv('TRADE_AMOUNT', '10.0')),
        'poll_interval': int(os.getenv('POLL_INTERVAL', '30'))
    },
    'current_opportunities': [],
    'recent_trades': [],
    'logs': []
}

bot_instance = None
bot_thread = None
bot_running = False


def add_log(message, log_type='info'):
    """Add a log entry and broadcast to frontend"""
    log_entry = {
        'message': message,
        'type': log_type,
        'time': datetime.now().strftime('%H:%M:%S')
    }
    bot_state['logs'].insert(0, log_entry)
    bot_state['logs'] = bot_state['logs'][:50]  # Keep last 50 logs
    
    # Broadcast to all connected clients
    socketio.emit('log', log_entry)


def load_markets():
    """Load markets from JSON file or fetch from API"""
    try:
        with open('token_ids.json', 'r') as f:
            markets = json.load(f)
            return markets
    except FileNotFoundError:
        add_log('token_ids.json not found. Run discover_markets.py first!', 'warning')
        return []


def update_runtime():
    """Update runtime statistics"""
    if bot_state['stats']['start_time']:
        elapsed = datetime.now() - bot_state['stats']['start_time']
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        bot_state['stats']['runtime'] = f"{hours}h {minutes}m"


def bot_loop():
    """Main bot trading loop"""
    global bot_instance, bot_running
    
    add_log('Initializing bot...', 'info')
    
    # Initialize bot
    try:
        private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
        signature_type = int(os.getenv('POLYMARKET_SIGNATURE_TYPE', '0'))
        funder = os.getenv('POLYMARKET_FUNDER')
        
        bot_instance = PolymarketBot(
            private_key=private_key,
            signature_type=signature_type,
            funder=funder
        )
        add_log('Bot initialized successfully', 'success')
    except Exception as e:
        add_log(f'Failed to initialize bot: {str(e)}', 'error')
        bot_state['status'] = 'error'
        return
    
    # Load markets
    markets = load_markets()
    if not markets:
        add_log('No markets loaded', 'error')
        bot_state['status'] = 'error'
        return
    
    # Filter valid markets
    valid_markets = [m for m in markets if len(m.get('tokens', [])) >= 2]
    add_log(f'Monitoring {len(valid_markets)} markets', 'info')
    
    bot_state['stats']['start_time'] = datetime.now()
    
    # Main loop
    while bot_running:
        try:
            update_runtime()
            
            # Check each market for arbitrage
            for market in valid_markets:
                if not bot_running:
                    break
                
                try:
                    tokens = market['tokens']
                    yes_token = tokens[0]['token_id']
                    no_token = tokens[1]['token_id']
                    
                    # Check for arbitrage
                    arb = bot_instance.check_arbitrage_opportunity(yes_token, no_token)
                    
                    if arb and arb['profit_pct'] >= bot_state['config']['min_profit']:
                        bot_state['stats']['opportunities_found'] += 1
                        
                        # Add to current opportunities
                        opportunity = {
                            'id': str(time.time()),
                            'market': market.get('question', 'Unknown Market'),
                            'yes_token': yes_token,
                            'no_token': no_token,
                            'yes_price': arb['yes_price'],
                            'no_price': arb['no_price'],
                            'profit': arb['profit'],
                            'profit_pct': arb['profit_pct'],
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        bot_state['current_opportunities'].insert(0, opportunity)
                        bot_state['current_opportunities'] = bot_state['current_opportunities'][:10]
                        
                        add_log(
                            f"Arbitrage found: {arb['profit_pct']:.2f}% profit on {market.get('question', 'Unknown')[:50]}",
                            'success'
                        )
                        
                        # Broadcast opportunity to frontend
                        socketio.emit('opportunity', opportunity)
                        
                        # Auto-execute if enabled (you can add this as a config option)
                        auto_execute = os.getenv('AUTO_EXECUTE', 'true').lower() == 'true'
                        
                        if auto_execute:
                            add_log(f"Executing trade for ${bot_state['config']['trade_amount']}", 'info')
                            
                            success = bot_instance.execute_arbitrage(
                                arb, 
                                bot_state['config']['trade_amount']
                            )
                            
                            if success:
                                expected_profit = arb['profit'] * bot_state['config']['trade_amount']
                                bot_state['stats']['trades_executed'] += 1
                                bot_state['stats']['total_profit'] += expected_profit
                                
                                # Add to recent trades
                                trade = {
                                    'id': str(time.time()),
                                    'market': market.get('question', 'Unknown'),
                                    'profit': expected_profit,
                                    'profit_pct': arb['profit_pct'],
                                    'timestamp': datetime.now().isoformat()
                                }
                                bot_state['recent_trades'].insert(0, trade)
                                bot_state['recent_trades'] = bot_state['recent_trades'][:20]
                                
                                add_log(f"Trade executed! Profit: ${expected_profit:.2f}", 'success')
                                socketio.emit('trade', trade)
                            else:
                                bot_state['stats']['failed_trades'] += 1
                                add_log('Trade execution failed', 'error')
                
                except Exception as e:
                    add_log(f'Error checking market: {str(e)}', 'error')
                    continue
            
            # Broadcast stats update
            socketio.emit('stats', bot_state['stats'])
            
            # Wait before next iteration
            add_log(f'Scan complete. Waiting {bot_state["config"]["poll_interval"]}s...', 'info')
            time.sleep(bot_state['config']['poll_interval'])
            
        except Exception as e:
            add_log(f'Error in bot loop: {str(e)}', 'error')
            time.sleep(bot_state['config']['poll_interval'])
    
    add_log('Bot stopped', 'warning')


# API Routes

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current bot status and stats"""
    return jsonify(bot_state)


@app.route('/api/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    global bot_thread, bot_running
    
    if bot_state['status'] == 'running':
        return jsonify({'error': 'Bot is already running'}), 400
    
    bot_running = True
    bot_state['status'] = 'running'
    
    # Start bot in background thread
    bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_thread.start()
    
    add_log('Bot started', 'success')
    
    return jsonify({'message': 'Bot started successfully'})


@app.route('/api/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    global bot_running
    
    if bot_state['status'] != 'running':
        return jsonify({'error': 'Bot is not running'}), 400
    
    bot_running = False
    bot_state['status'] = 'stopped'
    
    add_log('Stopping bot...', 'warning')
    
    return jsonify({'message': 'Bot stopped'})


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """Get or update bot configuration"""
    if request.method == 'GET':
        return jsonify(bot_state['config'])
    
    elif request.method == 'POST':
        data = request.json
        
        # Update config
        if 'min_profit' in data:
            bot_state['config']['min_profit'] = float(data['min_profit'])
        if 'trade_amount' in data:
            bot_state['config']['trade_amount'] = float(data['trade_amount'])
        if 'poll_interval' in data:
            bot_state['config']['poll_interval'] = int(data['poll_interval'])
        
        add_log('Configuration updated', 'info')
        
        return jsonify({'message': 'Configuration updated', 'config': bot_state['config']})


@app.route('/api/opportunities', methods=['GET'])
def get_opportunities():
    """Get current arbitrage opportunities"""
    return jsonify(bot_state['current_opportunities'])


@app.route('/api/trades', methods=['GET'])
def get_trades():
    """Get recent trades"""
    return jsonify(bot_state['recent_trades'])


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get activity logs"""
    return jsonify(bot_state['logs'])


@app.route('/api/execute', methods=['POST'])
def execute_trade():
    """Manually execute a specific trade"""
    data = request.json
    
    if not bot_instance:
        return jsonify({'error': 'Bot not initialized'}), 400
    
    yes_token = data.get('yes_token')
    no_token = data.get('no_token')
    amount = data.get('amount', bot_state['config']['trade_amount'])
    
    try:
        # Check arbitrage
        arb = bot_instance.check_arbitrage_opportunity(yes_token, no_token)
        
        if not arb:
            return jsonify({'error': 'No arbitrage opportunity found'}), 400
        
        # Execute
        success = bot_instance.execute_arbitrage(arb, amount)
        
        if success:
            expected_profit = arb['profit'] * amount
            bot_state['stats']['trades_executed'] += 1
            bot_state['stats']['total_profit'] += expected_profit
            
            add_log(f'Manual trade executed: ${expected_profit:.2f} profit', 'success')
            
            return jsonify({
                'message': 'Trade executed successfully',
                'profit': expected_profit
            })
        else:
            bot_state['stats']['failed_trades'] += 1
            return jsonify({'error': 'Trade execution failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# WebSocket events

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('status', bot_state)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


if __name__ == '__main__':
    print("="*70)
    print("Polymarket Bot API Server")
    print("="*70)
    print("API Server: http://localhost:5000")
    print("Dashboard will connect to this server")
    print("="*70)
    
    # Run with SocketIO
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
