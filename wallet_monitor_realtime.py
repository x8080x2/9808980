import logging
import threading
import time
from datetime import datetime
from web3 import Web3
from app import app, db
from models import WalletConfig, BalanceHistory, TelegramConfig, TransactionLog
from etherscan_api import EtherscanAPI
from telegram_bot import TelegramBot
from forwarding import check_for_incoming_payments

# Global variables for monitoring control
monitoring_thread = None
should_stop_monitoring = False
socketio_instance = None
last_heartbeat_time = 0

def start_realtime_monitoring(socketio):
    """Start simple real-time monitoring without blocking loops"""
    global socketio_instance
    socketio_instance = socketio

    logging.info("Real-time monitoring initialized (on-demand mode)")

    try:
        socketio.emit('log_event', {
            'source': 'Monitor',
            'message': 'Real-time monitoring initialized - checks on demand',
            'level': 'success'
        })
    except Exception as e:
        logging.error(f"Error emitting monitoring start event: {str(e)}")

def stop_realtime_monitoring():
    """Stop real-time monitoring"""
    global should_stop_monitoring, monitoring_thread, socketio_instance

    should_stop_monitoring = True
    socketio_instance = None

    logging.info("Real-time monitoring stopped")

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
            balance_history.balance_change = float(balance_change)
            balance_history.timestamp = datetime.utcnow()

            db.session.add(balance_history)
            db.session.commit()

            # Send notification if configured
            send_balance_notification(wallet_config, current_balance_eth, balance_change)

            logging.info(f"Balance updated for {wallet_config.address}: {current_balance_eth:.6f} ETH (change: {balance_change:+.6f})")

            return True
        else:
            # Update last checked time even if balance didn't change
            wallet_config.last_checked = datetime.utcnow()
            db.session.commit()

        return balance_changed

    except Exception as e:
        logging.error(f"Error checking balance for {wallet_config.address}: {str(e)}")
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

def send_balance_notification(wallet_config, current_balance_eth, balance_change):
    """Send balance notification via Telegram if configured"""
    try:
        telegram_config = TelegramConfig.query.first()
        if telegram_config and telegram_config.is_active:
            telegram_bot = TelegramBot(telegram_config.bot_token, telegram_config.chat_id)

            change_emoji = "📈" if balance_change > 0 else "📉"
            message = f"{change_emoji} Balance Update\n"
            message += f"Wallet: {wallet_config.address[:10]}...\n"
            message += f"Current: {current_balance_eth:.6f} ETH\n"
            message += f"Change: {balance_change:+.6f} ETH"

            telegram_bot.send_message(message)

    except Exception as e:
        logging.error(f"Error sending Telegram notification: {str(e)}")

def check_single_wallet_on_demand(wallet_address):
    """Check a single wallet balance on demand (called from WebSocket events)"""
    try:
        with app.app_context():
            wallet = WalletConfig.query.filter_by(address=wallet_address, is_active=True).first()
            if not wallet:
                return False

            balance_changed = check_wallet_balance_realtime(wallet, socketio_instance)

            if balance_changed and socketio_instance:
                emit_wallet_update(socketio_instance, wallet)

            return True

    except Exception as e:
        logging.error(f"Error in on-demand wallet check: {str(e)}")
        return False

# The following functions from the original code are no longer needed due to the refactoring:
# realtime_monitor_loop, check_latest_block, check_new_transactions
# They are omitted here as per the instructions to only include the necessary code.