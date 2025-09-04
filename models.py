from app import db
from datetime import datetime
from sqlalchemy import func

class WalletConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(42), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    check_interval = db.Column(db.Integer, default=300)  # seconds
    threshold_alert = db.Column(db.String(50), default="0.01")  # ETH
    last_balance = db.Column(db.String(50), default="0")
    last_checked = db.Column(db.DateTime)

class BalanceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_address = db.Column(db.String(42), db.ForeignKey('wallet_config.address'), nullable=False)
    balance = db.Column(db.String(50), nullable=False)
    balance_change = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notification_sent = db.Column(db.Boolean, default=False)

class TelegramConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_token = db.Column(db.String(200))
    chat_id = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TransactionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_address = db.Column(db.String(42), nullable=False)
    tx_hash = db.Column(db.String(66), unique=True, nullable=False)
    block_number = db.Column(db.Integer)
    from_address = db.Column(db.String(42))
    to_address = db.Column(db.String(42))
    value = db.Column(db.String(50))
    gas_used = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_incoming = db.Column(db.Boolean, default=False)
