#!/usr/bin/env node

const WebSocket = require('ws');
const fs = require('fs').promises;
const path = require('path');

class WebSocketMonitor {
    constructor(endpoints) {
        this.endpoints = endpoints; // Array of {name, url, chainId}
        this.connections = new Map();
        this.stats = new Map();
        this.logFile = `ws_monitor_${new Date().toISOString().split('T')[0]}.log`;
    }

    async start() {
        console.log(`Starting WebSocket Monitor for ${this.endpoints.length} endpoints`);
        console.log(`Logging to: ${this.logFile}\n`);

        // Initialize stats for each endpoint
        this.endpoints.forEach(endpoint => {
            this.stats.set(endpoint.name, {
                name: endpoint.name,
                url: endpoint.url,
                chainId: endpoint.chainId,
                connectionAttempts: 0,
                currentStatus: 'DISCONNECTED',
                lastConnected: null,
                lastDisconnected: null,
                lastError: null,
                reconnectCount: 0,
                messagesReceived: 0,
                currentBlock: 0,
                subscriptions: 0,
                uptime: 0,
                downtime: 0,
                lastStatusChange: Date.now()
            });
        });

        // Connect to all endpoints
        for (const endpoint of this.endpoints) {
            this.connectToEndpoint(endpoint);
        }

        // Start monitoring loop
        this.startMonitoringLoop();
    }

    connectToEndpoint(endpoint) {
        const stats = this.stats.get(endpoint.name);
        stats.connectionAttempts++;

        this.log(`[${endpoint.name}] Attempting connection...`);

        const ws = new WebSocket(endpoint.url, {
            timeout: 30000,
            handshakeTimeout: 10000
        });

        // Store connection
        this.connections.set(endpoint.name, ws);

        ws.on('open', () => {
            const previousStatus = stats.currentStatus;
            stats.currentStatus = 'CONNECTED';
            stats.lastConnected = Date.now();
            
            if (previousStatus === 'DISCONNECTED') {
                stats.reconnectCount++;
            }

            this.updateUptime(endpoint.name);
            this.log(`[${endpoint.name}] Connected successfully (attempt #${stats.connectionAttempts})`);

            // Get current block number
            ws.send(JSON.stringify({
                jsonrpc: '2.0',
                id: 1,
                method: 'eth_blockNumber',
                params: []
            }));

            // Subscribe to new blocks for heartbeat
            ws.send(JSON.stringify({
                jsonrpc: '2.0',
                id: 2,
                method: 'eth_subscribe',
                params: ['newHeads']
            }));
        });

        ws.on('message', (data) => {
            stats.messagesReceived++;
            
            try {
                const msg = JSON.parse(data);
                
                if (msg.id === 1 && msg.result) {
                    stats.currentBlock = parseInt(msg.result, 16);
                } else if (msg.id === 2 && msg.result) {
                    stats.subscriptions++;
                    this.log(`[${endpoint.name}] Subscription created: ${msg.result}`);
                } else if (msg.method === 'eth_subscription') {
                    // New block received - update current block
                    if (msg.params && msg.params.result && msg.params.result.number) {
                        stats.currentBlock = parseInt(msg.params.result.number, 16);
                    }
                }
            } catch (e) {
                // Ignore parse errors
            }
        });

        ws.on('error', (error) => {
            stats.lastError = {
                message: error.message,
                code: error.code,
                time: Date.now()
            };
            
            this.log(`[${endpoint.name}] ERROR: ${error.message}`);
        });

        ws.on('close', (code, reason) => {
            stats.currentStatus = 'DISCONNECTED';
            stats.lastDisconnected = Date.now();
            stats.subscriptions = 0;
            
            this.updateUptime(endpoint.name);
            this.log(`[${endpoint.name}] Disconnected: code=${code}, reason=${reason || 'unknown'}`);

            // Reconnect after delay
            setTimeout(() => {
                this.log(`[${endpoint.name}] Reconnecting...`);
                this.connectToEndpoint(endpoint);
            }, 5000);
        });

        ws.on('ping', () => {
            ws.pong();
        });
    }

    updateUptime(endpointName) {
        const stats = this.stats.get(endpointName);
        const now = Date.now();
        const duration = now - stats.lastStatusChange;

        if (stats.currentStatus === 'CONNECTED') {
            stats.uptime += duration;
        } else {
            stats.downtime += duration;
        }

        stats.lastStatusChange = now;
    }

    startMonitoringLoop() {
        // Print status every 30 seconds
        setInterval(() => {
            this.printStatus();
        }, 30000);

        // Save detailed stats every 5 minutes
        setInterval(() => {
            this.saveDetailedStats();
        }, 300000);

        // Initial status
        setTimeout(() => this.printStatus(), 2000);
    }

    printStatus() {
        console.clear();
        console.log('=== WebSocket Monitor Status ===');
        console.log(`Time: ${new Date().toISOString()}\n`);

        const table = [];
        
        for (const [name, stats] of this.stats) {
            const uptimePercent = stats.uptime + stats.downtime > 0 
                ? ((stats.uptime / (stats.uptime + stats.downtime)) * 100).toFixed(2)
                : '0.00';

            table.push({
                Endpoint: name,
                Status: stats.currentStatus,
                'Chain ID': stats.chainId,
                'Current Block': stats.currentBlock,
                'Uptime %': uptimePercent + '%',
                'Reconnects': stats.reconnectCount,
                'Messages': stats.messagesReceived,
                'Last Error': stats.lastError ? stats.lastError.message.substring(0, 30) + '...' : 'None'
            });
        }

        console.table(table);

        // Show alerts
        const alerts = [];
        for (const [name, stats] of this.stats) {
            if (stats.currentStatus === 'DISCONNECTED' && stats.lastDisconnected) {
                const downFor = Math.floor((Date.now() - stats.lastDisconnected) / 1000);
                if (downFor > 60) {
                    alerts.push(`⚠️  ${name} has been down for ${downFor} seconds`);
                }
            }
            
            if (stats.reconnectCount > 10) {
                alerts.push(`⚠️  ${name} has reconnected ${stats.reconnectCount} times`);
            }
        }

        if (alerts.length > 0) {
            console.log('\nALERTS:');
            alerts.forEach(alert => console.log(alert));
        }

        console.log('\nPress Ctrl+C to stop monitoring');
    }

    async saveDetailedStats() {
        const detailedStats = {};
        
        for (const [name, stats] of this.stats) {
            detailedStats[name] = {
                ...stats,
                timestamp: new Date().toISOString()
            };
        }

        const statsFile = `ws_stats_${new Date().toISOString().replace(/:/g, '-')}.json`;
        await fs.writeFile(statsFile, JSON.stringify(detailedStats, null, 2));
        this.log(`Saved detailed stats to ${statsFile}`);
    }

    async log(message) {
        const timestamp = new Date().toISOString();
        const logEntry = `${timestamp} ${message}\n`;
        
        // Write to file
        await fs.appendFile(this.logFile, logEntry).catch(() => {});
        
        // Also log critical errors to console
        if (message.includes('ERROR') || message.includes('CRITICAL')) {
            console.error(logEntry.trim());
        }
    }
}

// Parse command line arguments
function parseArgs() {
    const args = process.argv.slice(2);
    const endpoints = [];

    if (args.length === 0) {
        console.error('Usage: node monitor_ws_health.js <name>:<url>:<chainId> [<name>:<url>:<chainId> ...]');
        console.error('Example: node monitor_ws_health.js optimism:wss://opt-mainnet.g.alchemy.com/v2/key:10');
        process.exit(1);
    }

    for (const arg of args) {
        const parts = arg.split(':');
        if (parts.length < 4) { // name:wss:domain:path:chainId
            console.error(`Invalid format: ${arg}`);
            process.exit(1);
        }

        const name = parts[0];
        const url = parts.slice(1, -1).join(':'); // Rejoin URL parts
        const chainId = parseInt(parts[parts.length - 1]);

        endpoints.push({ name, url, chainId });
    }

    return endpoints;
}

// Handle shutdown gracefully
process.on('SIGINT', async () => {
    console.log('\n\nShutting down monitor...');
    
    const monitor = global.monitor;
    if (monitor) {
        await monitor.saveDetailedStats();
        
        // Close all connections
        for (const [name, ws] of monitor.connections) {
            if (ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
        }
    }
    
    process.exit(0);
});

// Start monitoring
const endpoints = parseArgs();
const monitor = new WebSocketMonitor(endpoints);
global.monitor = monitor; // Store reference for shutdown handler

monitor.start().catch(error => {
    console.error('Monitor error:', error);
    process.exit(1);
});