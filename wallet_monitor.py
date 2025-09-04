import logging
import os
from datetime import datetime
from web3 import Web3
from app import app, db
from models import WalletConfig, BalanceHistory, TelegramConfig
from etherscan_api import EtherscanAPI
from telegram_bot import TelegramBot
from apscheduler.triggers.interval import IntervalTrigger

def check_wallet_balance(wallet_config):
    """Check balance for a specific wallet and send notifications if needed"""
    try:
        with app.app_context():
            etherscan = EtherscanAPI()
            
            # Get current balance
            current_balance_wei = etherscan.get_balance(wallet_config.address)
            if current_balance_wei is None:
                logging.error(f"Failed to fetch balance for {wallet_config.address}")
                return False
            
            current_balance_eth = Web3.from_wei(int(current_balance_wei), 'ether')
            previous_balance_wei = wallet_config.last_balance if wallet_config.last_balance else "0"
            previous_balance_eth = Web3.from_wei(int(previous_balance_wei), 'ether') if previous_balance_wei.isdigit() else 0
            
            # Calculate balance change
            balance_change = current_balance_eth - previous_balance_eth
            
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
🔔 **Wallet Balance Alert**

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
                        logging.info(f"Notification sent for {wallet_config.address}")
                    else:
                        logging.error(f"Failed to send notification for {wallet_config.address}")
            
            db.session.add(balance_history)
            db.session.commit()
            
            logging.info(f"Balance check completed for {wallet_config.address}: {current_balance_eth:.6f} ETH")
            return True
            
    except Exception as e:
        logging.error(f"Error checking balance for {wallet_config.address}: {str(e)}")
        return False

def check_all_wallets():
    """Check balances for all active wallets"""
    try:
        with app.app_context():
            active_wallets = WalletConfig.query.filter_by(is_active=True).all()
            
            for wallet in active_wallets:
                try:
                    check_wallet_balance(wallet)
                except Exception as e:
                    logging.error(f"Error checking wallet {wallet.address}: {str(e)}")
                    
            logging.info(f"Completed balance check for {len(active_wallets)} wallets")
            
    except Exception as e:
        logging.error(f"Error in check_all_wallets: {str(e)}")

def start_monitoring(scheduler):
    """Start the background monitoring process"""
    try:
        # Add a job to check all wallets every 5 minutes
        scheduler.add_job(
            func=check_all_wallets,
            trigger=IntervalTrigger(minutes=5),
            id='wallet_balance_check',
            name='Check wallet balances',
            replace_existing=True
        )
        
        logging.info("Wallet monitoring started - checking every 5 minutes")
        
        # Run an initial check
        check_all_wallets()
        
    except Exception as e:
        logging.error(f"Error starting monitoring: {str(e)}")

def fetch_recent_transactions(wallet_address):
    """Fetch recent transactions for a wallet"""
    try:
        with app.app_context():
            from models import TransactionLog
            
            etherscan = EtherscanAPI()
            transactions = etherscan.get_transactions(wallet_address)
            
            if transactions:
                for tx in transactions[-10:]:  # Last 10 transactions
                    # Check if transaction already exists
                    existing_tx = TransactionLog.query.filter_by(tx_hash=tx['hash']).first()
                    
                    if not existing_tx:
                        tx_log = TransactionLog()
                        tx_log.wallet_address = wallet_address
                        tx_log.tx_hash = tx['hash']
                        tx_log.block_number = int(tx['blockNumber']) if tx['blockNumber'] else None
                        tx_log.from_address = tx['from']
                        tx_log.to_address = tx['to']
                        tx_log.value = tx['value']
                        tx_log.gas_used = tx['gasUsed']
                        tx_log.is_incoming = (tx['to'].lower() == wallet_address.lower())
                        tx_log.timestamp = datetime.fromtimestamp(int(tx['timeStamp']))
                        db.session.add(tx_log)
                
                db.session.commit()
                logging.info(f"Updated transactions for {wallet_address}")
                
    except Exception as e:
        logging.error(f"Error fetching transactions for {wallet_address}: {str(e)}")
