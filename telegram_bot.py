import requests
import logging
import os

class TelegramBot:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_message(self, message, parse_mode='Markdown'):
        """Send a message to the configured chat"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logging.info("Telegram message sent successfully")
                return True
            else:
                logging.error(f"Failed to send Telegram message: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending Telegram message: {str(e)}")
            return False
    
    def test_connection(self):
        """Test the Telegram bot connection"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    # Try to send a test message
                    test_message = "🤖 Ethereum Wallet Monitor connected successfully!"
                    return self.send_message(test_message)
            
            return False
            
        except Exception as e:
            logging.error(f"Error testing Telegram connection: {str(e)}")
            return False
    
    def send_balance_alert(self, wallet_address, current_balance, previous_balance, change):
        """Send a formatted balance change alert"""
        try:
            change_type = "📈 Increased" if change > 0 else "📉 Decreased"
            
            message = f"""
🔔 **Wallet Balance Alert**

**Address:** `{wallet_address}`
**Current Balance:** {current_balance:.6f} ETH
**Previous Balance:** {previous_balance:.6f} ETH
**{change_type}:** {abs(change):.6f} ETH

[View on Etherscan](https://etherscan.io/address/{wallet_address})
            """
            
            return self.send_message(message)
            
        except Exception as e:
            logging.error(f"Error sending balance alert: {str(e)}")
            return False
    
    def send_transaction_alert(self, wallet_address, tx_hash, is_incoming, value_eth):
        """Send a transaction alert"""
        try:
            direction = "Received" if is_incoming else "Sent"
            emoji = "📥" if is_incoming else "📤"
            
            message = f"""
{emoji} **New Transaction Detected**

**{direction}:** {value_eth:.6f} ETH
**Wallet:** `{wallet_address}`
**TX Hash:** `{tx_hash}`

[View Transaction](https://etherscan.io/tx/{tx_hash})
[View Wallet](https://etherscan.io/address/{wallet_address})
            """
            
            return self.send_message(message)
            
        except Exception as e:
            logging.error(f"Error sending transaction alert: {str(e)}")
            return False
