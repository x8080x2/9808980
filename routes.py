from flask import render_template, request, flash, redirect, url_for, jsonify
from app import app, db
from models import WalletConfig, BalanceHistory, TelegramConfig, TransactionLog
from web3 import Web3
from eth_account import Account
import os
import logging
from etherscan_api import EtherscanAPI
from telegram_bot import TelegramBot
from datetime import datetime, timedelta

@app.route('/')
def index():
    wallets = WalletConfig.query.filter_by(is_active=True).all()
    telegram_config = TelegramConfig.query.first()
    
    # Get recent balance history for chart
    recent_history = []
    if wallets:
        for wallet in wallets:
            history = BalanceHistory.query.filter_by(
                wallet_address=wallet.address
            ).order_by(BalanceHistory.timestamp.desc()).limit(10).all()
            recent_history.extend(history)
    
    return render_template('index.html', 
                         wallets=wallets, 
                         telegram_config=telegram_config,
                         recent_history=recent_history)

@app.route('/setup_wallet', methods=['POST'])
def setup_wallet():
    try:
        private_key = request.form.get('private_key', '').strip()
        threshold = request.form.get('threshold', '0.01')
        check_interval = int(request.form.get('check_interval', 300))
        
        if not private_key:
            # Try to get from environment
            private_key = os.getenv('ETH_PRIVATE_KEY', '')
            
        if not private_key:
            flash('Private key is required. Please provide it in the form or set ETH_PRIVATE_KEY environment variable.', 'error')
            return redirect(url_for('index'))
        
        # Ensure private key has proper format
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
            
        # Derive address from private key
        account = Account.from_key(private_key)
        address = account.address
        
        # Check if wallet already exists
        existing_wallet = WalletConfig.query.filter_by(address=address).first()
        if existing_wallet:
            existing_wallet.is_active = True
            existing_wallet.threshold_alert = threshold
            existing_wallet.check_interval = check_interval
            flash(f'Wallet {address} updated successfully!', 'success')
        else:
            # Create new wallet config
            wallet_config = WalletConfig()
            wallet_config.address = address
            wallet_config.threshold_alert = threshold
            wallet_config.check_interval = check_interval
            wallet_config.is_active = True
            db.session.add(wallet_config)
            flash(f'Wallet {address} added successfully!', 'success')
        
        db.session.commit()
        
    except Exception as e:
        logging.error(f"Error setting up wallet: {str(e)}")
        flash(f'Error setting up wallet: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/setup_telegram', methods=['POST'])
def setup_telegram():
    try:
        bot_token = request.form.get('bot_token', '').strip()
        chat_id = request.form.get('chat_id', '').strip()
        
        # Get from environment if not provided
        if not bot_token:
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        if not chat_id:
            chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
            
        if not bot_token or not chat_id:
            flash('Both Bot Token and Chat ID are required', 'error')
            return redirect(url_for('index'))
        
        # Test the telegram bot
        telegram_bot = TelegramBot(bot_token, chat_id)
        if telegram_bot.test_connection():
            # Update or create telegram config
            telegram_config = TelegramConfig.query.first()
            if telegram_config:
                telegram_config.bot_token = bot_token
                telegram_config.chat_id = chat_id
                telegram_config.is_active = True
            else:
                telegram_config = TelegramConfig()
                telegram_config.bot_token = bot_token
                telegram_config.chat_id = chat_id
                telegram_config.is_active = True
                db.session.add(telegram_config)
            
            db.session.commit()
            flash('Telegram bot configured successfully!', 'success')
        else:
            flash('Failed to connect to Telegram. Please check your bot token and chat ID.', 'error')
            
    except Exception as e:
        logging.error(f"Error setting up Telegram: {str(e)}")
        flash(f'Error setting up Telegram: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/wallet/<address>')
def wallet_details(address):
    wallet = WalletConfig.query.filter_by(address=address).first_or_404()
    
    # Get balance history
    history = BalanceHistory.query.filter_by(
        wallet_address=address
    ).order_by(BalanceHistory.timestamp.desc()).limit(100).all()
    
    # Get recent transactions
    transactions = TransactionLog.query.filter_by(
        wallet_address=address
    ).order_by(TransactionLog.timestamp.desc()).limit(50).all()
    
    # Get current balance from Etherscan
    try:
        etherscan = EtherscanAPI()
        current_balance = etherscan.get_balance(address)
        current_balance_eth = Web3.from_wei(int(current_balance) if current_balance else 0, 'ether')
    except Exception as e:
        logging.error(f"Error fetching current balance: {str(e)}")
        current_balance_eth = "Error fetching balance"
    
    return render_template('wallet_details.html', 
                         wallet=wallet, 
                         history=history, 
                         transactions=transactions,
                         current_balance=current_balance_eth)

@app.route('/toggle_wallet/<address>')
def toggle_wallet(address):
    wallet = WalletConfig.query.filter_by(address=address).first_or_404()
    wallet.is_active = not wallet.is_active
    db.session.commit()
    
    status = "activated" if wallet.is_active else "deactivated"
    flash(f'Wallet {address} {status}', 'info')
    return redirect(url_for('index'))

@app.route('/api/balance_history/<address>')
def api_balance_history(address):
    try:
        days = request.args.get('days', 7, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        history = BalanceHistory.query.filter(
            BalanceHistory.wallet_address == address,
            BalanceHistory.timestamp >= start_date
        ).order_by(BalanceHistory.timestamp.asc()).all()
        
        data = []
        for record in history:
            balance_eth = Web3.from_wei(int(record.balance), 'ether') if record.balance.isdigit() else 0
            data.append({
                'timestamp': record.timestamp.isoformat(),
                'balance': float(balance_eth),
                'balance_change': record.balance_change
            })
        
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error fetching balance history API: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/manual_check/<address>')
def manual_check(address):
    try:
        from wallet_monitor import check_wallet_balance
        wallet = WalletConfig.query.filter_by(address=address).first_or_404()
        
        result = check_wallet_balance(wallet)
        if result:
            flash(f'Manual check completed for {address}', 'success')
        else:
            flash(f'Manual check failed for {address}', 'error')
            
    except Exception as e:
        logging.error(f"Error in manual check: {str(e)}")
        flash(f'Error during manual check: {str(e)}', 'error')
    
    return redirect(url_for('index'))
