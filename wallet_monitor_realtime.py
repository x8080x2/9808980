import logging
import threading
import time
from datetime import datetime
from web3 import Web3
from app import app, db
from models import WalletConfig, BalanceHistory, TelegramConfig
from etherscan_api import EtherscanAPI
from telegram_bot import TelegramBot
from forwarding import check_for_incoming_payments

# Global thread control
monitoring_thread = None
should_stop_monitoring = False

def start_realtime_monitoring(socketio_instance):
    """Start real-time monitoring in a separate thread"""
    global monitoring_thread, should_stop_monitoring
    
    if monitoring_thread and monitoring_thread.is_alive():
        logging.info("Real-time monitoring already running")
        return
    
    should_stop_monitoring = False
    monitoring_thread = threading.Thread(
        target=realtime_monitor_loop,
        args=(socketio_instance,),
        daemon=True
    )
    monitoring_thread.start()
    logging.info("Real-time monitoring thread started")

def stop_realtime_monitoring():
    """Stop real-time monitoring"""
    global should_stop_monitoring
    should_stop_monitoring = True
    logging.info("Real-time monitoring stop requested")

def realtime_monitor_loop(socketio_instance):
    """Main monitoring loop that runs continuously"""
    global should_stop_monitoring
    
    logging.info("Starting real-time wallet monitoring loop")
    last_block_number = 0
    
    try:
        socketio_instance.emit('log_event', {
            'source': 'Monitor',
            'message': 'Real-time monitoring loop started',
            'level': 'success'
        })
    except:
        pass
    
    while not should_stop_monitoring:
        try:
            with app.app_context():
                # Check for new blocks first
                try:
                    current_block = check_latest_block(socketio_instance, last_block_number)
                    if current_block > last_block_number:
                        last_block_number = current_block
                except Exception as e:
                    logging.error(f"Error checking latest block: {str(e)}")
                
                active_wallets = WalletConfig.query.filter_by(is_active=True).all()
                
                # Emit monitoring heartbeat (less frequent to avoid spam)
                import time
                current_time = int(time.time())
                if not hasattr(realtime_monitor_loop, '_last_heartbeat') or current_time - realtime_monitor_loop._last_heartbeat > 60:  # Every minute
                    try:
                        socketio_instance.emit('log_event', {
                            'source': 'Monitor',
                            'message': f'⏰ Monitoring heartbeat: {len(active_wallets)} active wallets at block #{last_block_number}',
                            'level': 'info'
                        })
                        realtime_monitor_loop._last_heartbeat = current_time
                    except:
                        pass
                
                for wallet in active_wallets:
                    if should_stop_monitoring:
                        break
                        
                    try:
                        # Check for new transactions first
                        check_new_transactions(wallet, socketio_instance)
                        
                        # Then check balance changes
                        balance_changed = check_wallet_balance_realtime(wallet, socketio_instance)
                        
                        if balance_changed:
                            # Send real-time update to all connected clients
                            emit_wallet_update(socketio_instance, wallet)
                            
                    except Exception as e:
                        logging.error(f"Error checking wallet {wallet.address}: {str(e)}")
                        try:
                            socketio_instance.emit('log_event', {
                                'source': wallet.address,
                                'message': f"Error during balance check: {str(e)}",
                                'level': 'error'
                            })
                        except:
                            pass
                        
                # Small delay to prevent excessive API calls (check every 10 seconds)
                time.sleep(10)
                        
        except Exception as e:
            logging.error(f"Error in real-time monitoring loop: {str(e)}")
            time.sleep(30)  # Wait longer on errors
    
    logging.info("Real-time monitoring loop stopped")

def check_wallet_balance_realtime(wallet_config, socketio_instance):
    """Check balance for a specific wallet and return if balance changed"""
    try:
        etherscan = EtherscanAPI()
        
        # Get current balance
        current_balance_wei = etherscan.get_balance(wallet_config.address)
        if current_balance_wei is None:
            logging.error(f"Failed to fetch balance for {wallet_config.address}")
            return False
        
        current_balance_eth = Web3.from_wei(int(current_balance_wei), 'ether')
        previous_balance_wei = wallet_config.last_balance if wallet_config.last_balance else "0"
        previous_balance_eth = Web3.from_wei(int(previous_balance_wei), 'ether') if previous_balance_wei.isdigit() else 0
        
        # Check if balance has changed
        balance_change = current_balance_eth - previous_balance_eth
        balance_changed = abs(balance_change) > 0.000001  # Ignore tiny changes due to precision
        
        if balance_changed:
            # Check for incoming payments and trigger forwarding if enabled
            if wallet_config.forwarding_enabled and balance_change > 0:
                check_for_incoming_payments(wallet_config)
            
            # Update wallet config
            wallet_config.last_balance = current_balance_wei
            wallet_config.last_checked = datetime.utcnow()
            
            # Create balance history record
            balance_history = BalanceHistory()
            balance_history.wallet_address = wallet_config.address
            balance_history.balance = current_balance_wei
            balance_history.balance_change = str(Web3.to_wei(balance_change, 'ether'))
            
            # Check if notification should be sent
            threshold_wei = Web3.to_wei(float(wallet_config.threshold_alert), 'ether')
            should_notify = abs(Web3.to_wei(balance_change, 'ether')) >= threshold_wei
            
            if should_notify and balance_change != 0:
                # Send Telegram notification
                telegram_config = TelegramConfig.query.filter_by(is_active=True).first()
                if telegram_config:
                    telegram_bot = TelegramBot(telegram_config.bot_token, telegram_config.chat_id)
                    
                    change_type = "increased" if balance_change > 0 else "decreased"
                    message = f"""
🔔 **Real-time Wallet Balance Alert**

**Address:** `{wallet_config.address}`
**Current Balance:** {current_balance_eth:.6f} ETH
**Previous Balance:** {previous_balance_eth:.6f} ETH
**Change:** {balance_change:+.6f} ETH

Balance has {change_type} by {abs(balance_change):.6f} ETH
**Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

[View on Etherscan](https://etherscan.io/address/{wallet_config.address})
                    """
                    
                    if telegram_bot.send_message(message):
                        balance_history.notification_sent = True
                        logging.info(f"Real-time notification sent for {wallet_config.address}")
                    else:
                        logging.error(f"Failed to send real-time notification for {wallet_config.address}")
            
            db.session.add(balance_history)
            db.session.commit()
            
            logging.info(f"Real-time balance update for {wallet_config.address}: {current_balance_eth:.6f} ETH (change: {balance_change:+.6f})")
            
            # Emit detailed log event for monitoring
            try:
                change_type = "increased" if balance_change > 0 else "decreased"
                socketio_instance.emit('log_event', {
                    'source': wallet_config.address,
                    'message': f"💰 Balance {change_type}: {balance_change:+.6f} ETH → {current_balance_eth:.6f} ETH total",
                    'level': 'success' if balance_change > 0 else 'warning'
                })
                
                # Also emit a payment detection if threshold is met
                if should_notify and balance_change != 0:
                    socketio_instance.emit('log_event', {
                        'source': 'Alert',
                        'message': f"🚨 Threshold alert: {abs(balance_change):.6f} ETH {change_type} for {wallet_config.address[:10]}...",
                        'level': 'error' if balance_change < 0 else 'success'
                    })
            except:
                pass
        
        return balance_changed
        
    except Exception as e:
        logging.error(f"Error in real-time balance check for {wallet_config.address}: {str(e)}")
        return False

def check_latest_block(socketio_instance, last_known_block):
    """Check for new blocks and emit log events"""
    try:
        etherscan = EtherscanAPI()
        
        # Get current block number
        current_timestamp = int(time.time())
        current_block_str = etherscan.get_block_number_by_timestamp(current_timestamp, 'before')
        
        if current_block_str and current_block_str.isdigit():
            current_block = int(current_block_str)
            
            if current_block > last_known_block and last_known_block > 0:
                blocks_diff = current_block - last_known_block
                try:
                    socketio_instance.emit('log_event', {
                        'source': 'Blockchain',
                        'message': f'⛏️ New block(s) mined: #{current_block} (+{blocks_diff} blocks since last check)',
                        'level': 'info'
                    })
                    
                    # Also emit block monitor event for enhanced logging
                    socketio_instance.emit('block_monitor', {
                        'blockNumber': current_block,
                        'miner': 'Unknown',
                        'transactions': []
                    })
                except:
                    pass
                logging.info(f"New blocks detected: {last_known_block} -> {current_block}")
            
            return current_block
        
        return last_known_block
        
    except Exception as e:
        logging.error(f"Error checking latest block: {str(e)}")
        return last_known_block

def check_new_transactions(wallet_config, socketio_instance):
    """Check for new transactions for a wallet"""
    try:
        etherscan = EtherscanAPI()
        transactions = etherscan.get_transactions(wallet_config.address, page=1, offset=5)
        
        if not transactions:
            return
            
        # Check the most recent transaction
        latest_tx = transactions[0]
        tx_hash = latest_tx.get('hash', '')
        
        # Check if this is a new transaction we haven't seen
        if hasattr(wallet_config, '_last_tx_hash') and wallet_config._last_tx_hash == tx_hash:
            return  # Same transaction as before
            
        # Store the latest transaction hash
        wallet_config._last_tx_hash = tx_hash
        
        # Determine transaction direction
        is_incoming = latest_tx.get('to', '').lower() == wallet_config.address.lower()
        is_outgoing = latest_tx.get('from', '').lower() == wallet_config.address.lower()
        
        if is_incoming or is_outgoing:
            value_wei = int(latest_tx.get('value', '0'))
            value_eth = float(Web3.from_wei(value_wei, 'ether'))
            
            direction = "incoming" if is_incoming else "outgoing"
            other_address = latest_tx.get('from') if is_incoming else latest_tx.get('to')
            
            if value_eth > 0:  # Only log transactions with value
                try:
                    emoji = "📥" if is_incoming else "📤"
                    socketio_instance.emit('log_event', {
                        'source': wallet_config.address,
                        'message': f'{emoji} {direction.capitalize()} transaction: {value_eth:.6f} ETH {direction} {other_address[:10]}... (Block #{latest_tx.get("blockNumber", "pending")})',
                        'level': 'success' if is_incoming else 'warning'
                    })
                    
                    # Also emit detailed transaction event
                    socketio_instance.emit('transaction_monitor', {
                        'hash': tx_hash,
                        'from': latest_tx.get('from', ''),
                        'to': latest_tx.get('to', ''),
                        'value': f'{value_eth:.6f}',
                        'gasUsed': latest_tx.get('gasUsed', '0'),
                        'blockNumber': latest_tx.get('blockNumber', 'pending')
                    })
                except:
                    pass
                    
                logging.info(f"Transaction detected for {wallet_config.address}: {direction} {value_eth:.6f} ETH")
            
    except Exception as e:
        logging.error(f"Error checking transactions for {wallet_config.address}: {str(e)}")

def emit_wallet_update(socketio_instance, wallet_config):
    """Emit real-time wallet update to all connected clients"""
    try:
        current_balance_eth = float(Web3.from_wei(int(wallet_config.last_balance), 'ether'))
        
        update_data = {
            'address': wallet_config.address,
            'balance': current_balance_eth,
            'last_checked': wallet_config.last_checked.isoformat() if wallet_config.last_checked else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        socketio_instance.emit('balance_update', update_data)
        logging.info(f"Emitted real-time balance update for {wallet_config.address}")
        
    except Exception as e:
        logging.error(f"Error emitting wallet update: {str(e)}")