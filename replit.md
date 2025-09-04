# Overview

This is an Ethereum Wallet Monitor application built with Flask that provides real-time monitoring of Ethereum wallet balances and transaction activity. The system tracks wallet balances, sends notifications when changes exceed configured thresholds, and maintains historical data for analysis. It integrates with the Etherscan API for blockchain data retrieval and Telegram for instant notifications.

## Current Status
- **Application**: Running and operational on port 5000
- **Monitored Wallets**: 2 active wallets
  - Wallet 1: 0x22c895e98bf856B9BE92d1b012bf3aB5ba88c47C (Threshold: 0.01 ETH)
  - Wallet 2: 0xF321ED7E83ce0828078d07852A11ece4332A32eb (Threshold: 0.01 ETH)
- **Etherscan API**: Configured and working
- **Monitoring**: Active with 5-minute check intervals
- **Telegram**: Ready for configuration

## Wallet Details
Private keys have been securely processed to derive wallet addresses. The monitoring system tracks balance changes and will send alerts when changes exceed the 0.01 ETH threshold.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Framework
- **Flask-based web application** with SQLAlchemy ORM for database operations
- **Background scheduling** using APScheduler for automated wallet monitoring tasks
- **Modular design** with separate modules for API interactions, database models, and monitoring logic

## Database Design
- **SQLAlchemy with SQLite** as the default database (configurable via DATABASE_URL environment variable)
- **Four main entities**: WalletConfig for wallet settings, BalanceHistory for tracking changes, TelegramConfig for notification settings, and TransactionLog for transaction records
- **Connection pooling** with automatic reconnection handling for reliability

## External API Integration
- **Etherscan API client** with built-in rate limiting (5 calls per second) and error handling
- **Web3 integration** for Ethereum address derivation from private keys and wei/ether conversions
- **Telegram Bot API** for sending real-time notifications with markdown formatting support

## Monitoring System
- **Automated balance checking** with configurable intervals per wallet
- **Threshold-based alerting** that triggers notifications when balance changes exceed user-defined limits
- **Historical tracking** of all balance changes with timestamps for trend analysis

## Frontend Architecture
- **Bootstrap-based responsive UI** with dark theme support
- **Chart.js integration** for visualizing balance history and trends
- **Feather icons** for consistent iconography throughout the interface

## Security Considerations
- **Environment variable storage** for sensitive data like private keys and API tokens
- **Private key derivation** to wallet addresses without storing keys in the database
- **Secure session management** with configurable secret keys

# External Dependencies

## Blockchain Services
- **Etherscan API** - Primary data source for Ethereum blockchain information including balances and transaction history
- **Web3 Python library** - For Ethereum address validation and cryptocurrency unit conversions

## Notification Services  
- **Telegram Bot API** - Real-time notification delivery system for balance alerts and transaction notifications

## Database
- **SQLite** (default) - Local database storage with configurable support for PostgreSQL via DATABASE_URL
- **SQLAlchemy** - ORM layer providing database abstraction and connection management

## Frontend Libraries
- **Bootstrap CSS Framework** - UI components and responsive design system
- **Chart.js** - Interactive charts for displaying balance history and trends  
- **Feather Icons** - Lightweight icon library for user interface elements

## Background Processing
- **APScheduler** - Task scheduling system for automated wallet monitoring and balance checking operations