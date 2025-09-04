// Ethereum Wallet Monitor - Main JavaScript

class WalletMonitor {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.init();
    }

    init() {
        // Initialize components
        this.setupEventListeners();
        this.setupAutoRefresh();
        this.setupFormValidation();
        
        // Initialize tooltips and popovers
        this.initializeBootstrapComponents();
        
        // Initialize real-time monitoring
        this.initializeWebSocket();
    }

    setupEventListeners() {
        // Copy to clipboard functionality
        document.addEventListener('click', (e) => {
            if (e.target.closest('.copy-btn')) {
                this.copyToClipboard(e);
            }
        });

        // Form submission handling
        document.addEventListener('submit', (e) => {
            if (e.target.classList.contains('wallet-form')) {
                this.handleWalletForm(e);
            }
        });

        // Manual refresh buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('.refresh-btn')) {
                this.handleManualRefresh(e);
            }
        });
    }

    setupAutoRefresh() {
        // Auto-refresh dashboard every 30 seconds
        if (window.location.pathname === '/') {
            setInterval(() => {
                this.refreshDashboard();
            }, 30000);
        }
    }

    setupFormValidation() {
        // Private key validation
        const privateKeyInputs = document.querySelectorAll('input[name="private_key"]');
        privateKeyInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                this.validatePrivateKey(e.target);
            });
        });

        // Threshold validation
        const thresholdInputs = document.querySelectorAll('input[name="threshold"]');
        thresholdInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                this.validateThreshold(e.target);
            });
        });
    }

    validatePrivateKey(input) {
        const value = input.value.trim();
        const isValid = value === '' || this.isValidPrivateKey(value);
        
        input.classList.toggle('is-invalid', !isValid);
        input.classList.toggle('is-valid', isValid && value !== '');
    }

    isValidPrivateKey(key) {
        // Remove 0x prefix if present
        const cleanKey = key.startsWith('0x') ? key.slice(2) : key;
        
        // Check if it's a valid hex string of 64 characters
        return /^[a-fA-F0-9]{64}$/.test(cleanKey);
    }

    validateThreshold(input) {
        const value = parseFloat(input.value);
        const isValid = !isNaN(value) && value >= 0;
        
        input.classList.toggle('is-invalid', !isValid);
        input.classList.toggle('is-valid', isValid);
    }

    copyToClipboard(event) {
        const button = event.target.closest('.copy-btn');
        const textToCopy = button.dataset.text || button.previousElementSibling.textContent;
        
        navigator.clipboard.writeText(textToCopy).then(() => {
            this.showCopySuccess(button);
        }).catch(err => {
            console.error('Failed to copy text: ', err);
            this.showCopyError(button);
        });
    }

    showCopySuccess(button) {
        const originalHTML = button.innerHTML;
        button.innerHTML = '<i data-feather="check" width="16" height="16"></i>';
        button.classList.add('btn-success');
        
        // Replace feather icons
        feather.replace();
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('btn-success');
            feather.replace();
        }, 2000);
    }

    showCopyError(button) {
        const originalHTML = button.innerHTML;
        button.innerHTML = '<i data-feather="x" width="16" height="16"></i>';
        button.classList.add('btn-danger');
        
        feather.replace();
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('btn-danger');
            feather.replace();
        }, 2000);
    }

    handleWalletForm(event) {
        const form = event.target;
        const submitButton = form.querySelector('button[type="submit"]');
        
        // Add loading state
        this.setButtonLoading(submitButton, true);
        
        // Form will submit normally, loading state will be reset on page reload
    }

    handleManualRefresh(event) {
        event.preventDefault();
        const button = event.target.closest('.refresh-btn');
        const originalHTML = button.innerHTML;
        
        // Set loading state
        button.innerHTML = '<i data-feather="loader" width="16" height="16"></i>';
        button.classList.add('loading');
        
        feather.replace();
        
        // Navigate to the refresh URL
        setTimeout(() => {
            window.location.href = button.href;
        }, 500);
    }

    setButtonLoading(button, loading) {
        if (loading) {
            button.disabled = true;
            button.classList.add('loading');
        } else {
            button.disabled = false;
            button.classList.remove('loading');
        }
    }

    refreshDashboard() {
        // Only refresh if user is active (not away from page)
        if (!document.hidden) {
            // Check if there are any form inputs being edited
            const activeElement = document.activeElement;
            const isFormActive = activeElement && (
                activeElement.tagName === 'INPUT' || 
                activeElement.tagName === 'TEXTAREA' || 
                activeElement.tagName === 'SELECT'
            );
            
            // Don't refresh if user is actively editing a form
            if (!isFormActive) {
                location.reload();
            }
        }
    }

    initializeBootstrapComponents() {
        // Initialize tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        // Initialize popovers
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }

    // Utility method to format large numbers
    formatNumber(num, decimals = 6) {
        if (num === 0) return '0';
        
        const absNum = Math.abs(num);
        if (absNum >= 1000000) {
            return (num / 1000000).toFixed(2) + 'M';
        } else if (absNum >= 1000) {
            return (num / 1000).toFixed(2) + 'K';
        } else if (absNum >= 1) {
            return num.toFixed(decimals);
        } else {
            return num.toFixed(decimals);
        }
    }

    // Utility method to format timestamps
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);
        
        if (days > 0) {
            return `${days}d ago`;
        } else if (hours > 0) {
            return `${hours}h ago`;
        } else if (minutes > 0) {
            return `${minutes}m ago`;
        } else {
            return 'Just now';
        }
    }

    // Method to show notifications
    showNotification(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container');
        container.insertBefore(alertDiv, container.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }

    initializeWebSocket() {
        if (typeof io === 'undefined') {
            console.log('[INFO] Socket.IO not available, skipping real-time monitoring');
            return;
        }

        try {
            this.socket = io();
            this.setupSocketListeners();
            console.log('[INFO] Connecting to real-time monitoring...');
        } catch (error) {
            console.error('[ERROR] Failed to initialize WebSocket:', error);
        }
    }

    setupSocketListeners() {
        if (!this.socket) return;

        // Connection events
        this.socket.on('connect', () => {
            this.connected = true;
            console.log('Connected to real-time monitoring');
            this.updateConnectionStatus(true);
            
            // Automatically start monitoring
            this.socket.emit('start_monitoring');
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            console.log('[WARNING] Disconnected from real-time monitoring');
            this.updateConnectionStatus(false);
        });

        // Wallet status updates
        this.socket.on('wallet_status', (wallets) => {
            console.log('Initial wallet status received:', wallets);
            this.updateWalletStatus(wallets);
        });

        // Balance updates
        this.socket.on('balance_update', (data) => {
            console.log('Balance update received:', data);
            this.updateWalletBalance(data);
        });

        // Log events for notifications
        this.socket.on('log_event', (data) => {
            if (data.level === 'success' && data.message.includes('Balance')) {
                this.showNotification(data.message, 'success');
            } else if (data.level === 'error') {
                this.showNotification(data.message, 'danger');
            }
        });

        // Monitoring status
        this.socket.on('monitoring_status', (data) => {
            console.log('Monitoring status:', data);
            if (data.status === 'started') {
                this.showNotification('Real-time monitoring started', 'success');
            }
        });
    }

    updateConnectionStatus(connected) {
        // Update any connection indicators in the UI
        const indicators = document.querySelectorAll('.connection-status');
        indicators.forEach(indicator => {
            indicator.className = `connection-status ${connected ? 'text-success' : 'text-danger'}`;
            indicator.textContent = connected ? 'Connected' : 'Disconnected';
        });
    }

    updateWalletStatus(wallets) {
        wallets.forEach(wallet => {
            this.updateWalletBalance({
                address: wallet.address,
                balance: wallet.balance,
                timestamp: new Date().toISOString()
            });
        });
    }

    updateWalletBalance(data) {
        // Find wallet row in the table
        const walletRows = document.querySelectorAll('tr[data-wallet-address]');
        walletRows.forEach(row => {
            const address = row.getAttribute('data-wallet-address');
            if (address === data.address) {
                // Update balance display
                const balanceCell = row.querySelector('.wallet-balance');
                if (balanceCell) {
                    balanceCell.textContent = `${parseFloat(data.balance).toFixed(6)} ETH`;
                    balanceCell.classList.add('text-success');
                    setTimeout(() => {
                        balanceCell.classList.remove('text-success');
                    }, 2000);
                }

                // Update last checked time
                const lastCheckedCell = row.querySelector('.last-checked');
                if (lastCheckedCell) {
                    lastCheckedCell.textContent = this.formatTime(data.timestamp);
                }
            }
        });

        // Update any wallet cards
        const walletCards = document.querySelectorAll('.wallet-card');
        walletCards.forEach(card => {
            const address = card.getAttribute('data-wallet-address');
            if (address === data.address) {
                const balanceElement = card.querySelector('.wallet-balance');
                if (balanceElement) {
                    balanceElement.textContent = `${parseFloat(data.balance).toFixed(6)} ETH`;
                }
            }
        });
    }
}

// Initialize the wallet monitor when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.walletMonitor = new WalletMonitor();
    
    // Initialize feather icons
    feather.replace();
});

// Export for use in other scripts
window.WalletMonitor = WalletMonitor;
