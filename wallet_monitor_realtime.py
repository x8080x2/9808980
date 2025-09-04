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
    
    while not should_stop_monitoring:
        try:
            with app.app_context():
                active_wallets = WalletConfig.query.filter_by(is_active=True).all()
                
                for wallet in active_wallets:
                    if should_stop_monitoring:
                        break
                        
                    try:
                        balance_changed = check_wallet_balance_realtime(wallet, socketio_instance)
                        
                        if balance_changed:
                            # Send real-time update to all connected clients
                            emit_wallet_update(socketio_instance, wallet)
                            
                    except Exception as e:
                        logging.error(f"Error checking wallet {wallet.address}: {str(e)}")
                        
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
        
        return balance_changed
        
    except Exception as e:
        logging.error(f"Error in real-time balance check for {wallet_config.address}: {str(e)}")
        return False

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