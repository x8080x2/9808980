
import logging
import os
from decimal import Decimal
from web3 import Web3
from eth_account import Account
from app import app, db
from models import WalletConfig, TransactionLog
from etherscan_api import EtherscanAPI
from telegram_bot import TelegramBot
from models import TelegramConfig
from datetime import datetime

def forward_payment(wallet_config, amount_wei):
    """Forward payment from monitored wallet to receiver wallet"""
    try:
        receiver_address = os.getenv('RECEIVER_WALLET_ADDRESS')
        if not receiver_address:
            logging.error("RECEIVER_WALLET_ADDRESS not set in environment variables")
            return False
        
        # Initialize Web3 connection
        w3 = Web3(Web3.HTTPProvider(os.getenv('ETH_RPC_URL', 'https://mainnet.infura.io/v3/YOUR_INFURA_KEY')))
        
        if not w3.is_connected():
            logging.error("Failed to connect to Ethereum network")
            return False
        
        # Load account from private key stored in environment variable
        private_key = os.getenv(f'ETH_PRIVATE_KEY_{wallet_config.address}')
        if not private_key:
            logging.error(f"Private key not found in environment variables for {wallet_config.address}")
            return False
        account = Account.from_key(private_key)
        
        # Get current gas price
        gas_price = w3.eth.gas_price
        
        # Estimate gas for simple transfer
        gas_limit = 21000
        gas_cost = gas_price * gas_limit
        
        # Get current balance and calculate amount to send
        current_balance = w3.eth.get_balance(wallet_config.address)
        
        # Keep a threshold amount in the wallet (use threshold_alert as keep amount)
        keep_threshold_wei = Web3.to_wei(Decimal(wallet_config.threshold_alert), 'ether')
        
        # Calculate amount to send: Total Balance - Gas Cost - Keep Threshold
        amount_to_send = current_balance - gas_cost - keep_threshold_wei
        
        # Check if we have enough to send after keeping threshold and gas
        if amount_to_send <= 0:
            logging.info(f"Insufficient balance to forward after keeping {wallet_config.threshold_alert} ETH threshold and gas costs for {wallet_config.address}")
            return False
        
        logging.info(f"Forwarding {Web3.from_wei(amount_to_send, 'ether')} ETH from {wallet_config.address}, keeping {wallet_config.threshold_alert} ETH + gas")
        
        # Build transaction
        transaction = {
            'to': receiver_address,
            'value': amount_to_send,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': w3.eth.get_transaction_count(wallet_config.address),
        }
        
        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=private_key)
        
        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_hash_hex = tx_hash.hex()
        
        logging.info(f"Forwarding transaction sent: {tx_hash_hex}")
        
        # Log the forwarding transaction
        tx_log = TransactionLog()
        tx_log.wallet_address = wallet_config.address
        tx_log.tx_hash = tx_hash_hex
        tx_log.from_address = wallet_config.address
        tx_log.to_address = receiver_address
        tx_log.value = str(amount_to_send)
        tx_log.gas_used = str(gas_limit)
        tx_log.is_incoming = False
        tx_log.timestamp = datetime.utcnow()
        db.session.add(tx_log)
        db.session.commit()
        
        # Send notification
        send_forwarding_notification(wallet_config, amount_to_send, tx_hash_hex, receiver_address)
        
        return True
        
    except Exception as e:
        logging.error(f"Error forwarding payment from {wallet_config.address}: {str(e)}")
        return False

def send_forwarding_notification(wallet_config, amount_wei, tx_hash, receiver_address):
    """Send Telegram notification about forwarding"""
    try:
        telegram_config = TelegramConfig.query.filter_by(is_active=True).first()
        if not telegram_config:
            return
        
        telegram_bot = TelegramBot(telegram_config.bot_token, telegram_config.chat_id)
        amount_eth = Web3.from_wei(amount_wei, 'ether')
        
        message = f"""
🔄 **Payment Forwarded**

**From:** `{wallet_config.address}`
**To:** `{receiver_address}`
**Amount:** {amount_eth:.6f} ETH
**Transaction:** `{tx_hash}`
**Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

[View Transaction](https://etherscan.io/tx/{tx_hash})
        """
        
        telegram_bot.send_message(message)
        logging.info(f"Forwarding notification sent for {wallet_config.address}")
        
    except Exception as e:
        logging.error(f"Error sending forwarding notification: {str(e)}")

def check_for_incoming_payments(wallet_config):
    """Check for new incoming payments and trigger forwarding of ALL funds except threshold"""
    try:
        etherscan = EtherscanAPI()
        transactions = etherscan.get_transactions(wallet_config.address)
        
        if not transactions:
            return
        
        # Check recent transactions (last 5)
        recent_txs = transactions[-5:]
        
        for tx in recent_txs:
            # Check if it's an incoming transaction
            if tx['to'].lower() == wallet_config.address.lower():
                # Check if we've already processed this transaction
                existing_tx = TransactionLog.query.filter_by(tx_hash=tx['hash']).first()
                
                if not existing_tx and wallet_config.forwarding_enabled:
                    # New incoming payment detected
                    amount_wei = int(tx['value'])
                    
                    logging.info(f"New incoming payment detected: {Web3.from_wei(amount_wei, 'ether')} ETH to {wallet_config.address}")
                    
                    # Trigger forwarding of ALL available funds (except threshold)
                    if forward_payment(wallet_config, amount_wei):
                        logging.info(f"All available funds forwarded successfully from {wallet_config.address}")
                    else:
                        logging.error(f"Failed to forward funds from {wallet_config.address}")
                
    except Exception as e:
        logging.error(f"Error checking for incoming payments: {str(e)}")
