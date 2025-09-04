import requests
import logging
import os
import time
from typing import Optional, List, Dict

class EtherscanAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('ETHERSCAN_API_KEY', '')
        self.base_url = "https://api.etherscan.io/api"
        self.rate_limit_delay = 0.2  # 5 calls per second for free tier

    def _make_request(self, params):
        """Make a rate-limited request to Etherscan API"""
        try:
            if not self.api_key:
                logging.warning("Etherscan API key not configured. Set ETHERSCAN_API_KEY environment variable.")
                return None

            params['apikey'] = self.api_key
            response = requests.get(self.base_url, params=params, timeout=10)

            # Rate limiting
            time.sleep(self.rate_limit_delay)

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    return data.get('result')
                else:
                    logging.error(f"Etherscan API error: {data.get('message', 'Unknown error')}")
                    return None
            else:
                logging.error(f"HTTP error: {response.status_code}")
                return None

        except Exception as e:
            logging.error(f"Error making Etherscan API request: {str(e)}")
            return None

    def get_balance(self, address: str) -> Optional[str]:
        """Get ETH balance for an address"""
        params = {
            'module': 'account',
            'action': 'balance',
            'address': address,
            'tag': 'latest'
        }

        result = self._make_request(params)
        return result if result is not None else "0"

    def get_multiple_balances(self, addresses: List[str]) -> Optional[List[Dict]]:
        """Get ETH balances for multiple addresses (max 20)"""
        if len(addresses) > 20:
            logging.warning("Too many addresses, limiting to first 20")
            addresses = addresses[:20]

        params = {
            'module': 'account',
            'action': 'balancemulti',
            'address': ','.join(addresses),
            'tag': 'latest'
        }

        return self._make_request(params)

    def get_token_balance(self, contract_address: str, wallet_address: str) -> Optional[str]:
        """Get ERC-20 token balance for an address"""
        params = {
            'module': 'account',
            'action': 'tokenbalance',
            'contractaddress': contract_address,
            'address': wallet_address,
            'tag': 'latest'
        }

        result = self._make_request(params)
        return result if result is not None else "0"

    def get_transactions(self, address: str, start_block: int = 0, end_block: int = 99999999,
                        page: int = 1, offset: int = 100) -> Optional[List[Dict]]:
        """Get list of normal transactions for an address"""
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'page': page,
            'offset': offset,
            'sort': 'desc'
        }

        return self._make_request(params)

    def get_internal_transactions(self, address: str, start_block: int = 0, end_block: int = 99999999,
                                page: int = 1, offset: int = 100) -> Optional[List[Dict]]:
        """Get list of internal transactions for an address"""
        params = {
            'module': 'account',
            'action': 'txlistinternal',
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'page': page,
            'offset': offset,
            'sort': 'desc'
        }

        return self._make_request(params)

    def get_token_transfers(self, address: str, contract_address: Optional[str] = None,
                          start_block: int = 0, end_block: int = 99999999,
                          page: int = 1, offset: int = 100) -> Optional[List[Dict]]:
        """Get list of ERC-20 token transfers for an address"""
        params = {
            'module': 'account',
            'action': 'tokentx',
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'page': page,
            'offset': offset,
            'sort': 'desc'
        }

        if contract_address:
            params['contractaddress'] = contract_address

        return self._make_request(params)

    def get_gas_price(self) -> Optional[str]:
        """Get current gas price"""
        params = {
            'module': 'gastracker',
            'action': 'gasoracle'
        }

        result = self._make_request(params)
        if result and isinstance(result, dict):
            return result.get('SafeGasPrice', '0')
        return "0"

    def get_eth_price(self) -> Optional[Dict]:
        """Get current ETH price in USD"""
        params = {
            'module': 'stats',
            'action': 'ethprice'
        }

        return self._make_request(params)

    def get_block_number_by_timestamp(self, timestamp: int, closest: str = 'before') -> Optional[str]:
        """Get block number by timestamp"""
        params = {
            'module': 'block',
            'action': 'getblocknobytime',
            'timestamp': timestamp,
            'closest': closest
        }

        return self._make_request(params)