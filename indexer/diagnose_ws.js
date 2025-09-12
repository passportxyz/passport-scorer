#!/usr/bin/env node

const WebSocket = require('ws');
const https = require('https');
const dns = require('dns').promises;
const { URL } = require('url');

class WebSocketDiagnostics {
    constructor(wsUrl) {
        this.wsUrl = wsUrl;
        this.stats = {
            connectionAttempts: 0,
            successfulConnections: 0,
            errors: [],
            latencies: [],
            messagesReceived: 0,
            messagesSent: 0,
            disconnects: 0,
            lastError: null,
            connectionStartTime: null,
            subscriptions: new Map()
        };
    }

    async runFullDiagnostics() {
        console.log('=== WebSocket Diagnostics Tool ===');
        console.log(`URL: ${this.wsUrl}`);
        console.log(`Time: ${new Date().toISOString()}\n`);

        // 1. DNS Resolution Test
        await this.testDnsResolution();

        // 2. HTTPS Connectivity Test
        await this.testHttpsEndpoint();

        // 3. WebSocket Connection Test
        await this.testWebSocketConnection();

        // 4. Subscription Test
        await this.testSubscriptions();

        // 5. Long-running stability test
        await this.testLongRunningConnection();

        // Print final report
        this.printReport();
    }

    async testDnsResolution() {
        console.log('1. Testing DNS Resolution...');
        try {
            const url = new URL(this.wsUrl);
            const hostname = url.hostname;
            const addresses = await dns.resolve4(hostname);
            console.log(`   ✓ DNS resolved ${hostname} to: ${addresses.join(', ')}`);
        } catch (error) {
            console.log(`   ✗ DNS resolution failed: ${error.message}`);
            this.stats.errors.push({ type: 'DNS', message: error.message });
        }
        console.log('');
    }

    async testHttpsEndpoint() {
        console.log('2. Testing HTTPS Endpoint...');
        const httpsUrl = this.wsUrl.replace('wss://', 'https://').replace('ws://', 'http://');
        
        return new Promise((resolve) => {
            const startTime = Date.now();
            https.get(httpsUrl, (res) => {
                const latency = Date.now() - startTime;
                console.log(`   ✓ HTTPS endpoint responded with status: ${res.statusCode}`);
                console.log(`   ✓ Response time: ${latency}ms`);
                console.log(`   ✓ Headers: ${JSON.stringify(res.headers['upgrade'] || 'none')}`);
                resolve();
            }).on('error', (error) => {
                console.log(`   ✗ HTTPS request failed: ${error.message}`);
                this.stats.errors.push({ type: 'HTTPS', message: error.message });
                resolve();
            });
            console.log('');
        });
    }

    async testWebSocketConnection() {
        console.log('3. Testing WebSocket Connection...');
        
        return new Promise((resolve) => {
            const startTime = Date.now();
            this.stats.connectionAttempts++;
            
            const ws = new WebSocket(this.wsUrl, {
                timeout: 30000,
                handshakeTimeout: 10000
            });

            let connectionTimeout = setTimeout(() => {
                console.log('   ✗ Connection timeout after 30 seconds');
                ws.terminate();
                resolve();
            }, 30000);

            ws.on('open', () => {
                clearTimeout(connectionTimeout);
                const latency = Date.now() - startTime;
                this.stats.latencies.push(latency);
                this.stats.successfulConnections++;
                console.log(`   ✓ Connected successfully in ${latency}ms`);
                
                // Test basic RPC
                const testRequest = {
                    jsonrpc: '2.0',
                    id: 1,
                    method: 'eth_blockNumber',
                    params: []
                };
                
                console.log('   → Sending test request: eth_blockNumber');
                ws.send(JSON.stringify(testRequest));
                this.stats.messagesSent++;
            });

            ws.on('message', (data) => {
                this.stats.messagesReceived++;
                try {
                    const response = JSON.parse(data);
                    if (response.id === 1) {
                        console.log(`   ✓ Received response: block ${parseInt(response.result, 16)}`);
                        ws.close();
                        resolve();
                    }
                } catch (e) {
                    console.log(`   ⚠ Received non-JSON message: ${data}`);
                }
            });

            ws.on('error', (error) => {
                clearTimeout(connectionTimeout);
                console.log(`   ✗ WebSocket error: ${error.message}`);
                this.stats.errors.push({ 
                    type: 'WebSocket', 
                    message: error.message,
                    code: error.code,
                    errno: error.errno
                });
                this.stats.lastError = error;
                resolve();
            });

            ws.on('close', (code, reason) => {
                clearTimeout(connectionTimeout);
                console.log(`   → Connection closed: code=${code}, reason=${reason || 'none'}`);
                this.stats.disconnects++;
                resolve();
            });
        });
        console.log('');
    }

    async testSubscriptions() {
        console.log('4. Testing Subscriptions...');
        
        return new Promise((resolve) => {
            const ws = new WebSocket(this.wsUrl);
            let subscriptionId = null;
            let eventsReceived = 0;
            
            ws.on('open', () => {
                console.log('   ✓ Connected');
                
                // Subscribe to new blocks
                const subRequest = {
                    jsonrpc: '2.0',
                    id: 2,
                    method: 'eth_subscribe',
                    params: ['newHeads']
                };
                
                console.log('   → Creating subscription for new blocks');
                ws.send(JSON.stringify(subRequest));
            });

            ws.on('message', (data) => {
                const response = JSON.parse(data);
                
                if (response.id === 2) {
                    subscriptionId = response.result;
                    console.log(`   ✓ Subscription created: ${subscriptionId}`);
                    console.log('   → Waiting for events (30 seconds)...');
                    
                    // Wait 30 seconds for events
                    setTimeout(() => {
                        console.log(`   → Received ${eventsReceived} events in 30 seconds`);
                        
                        // Unsubscribe
                        const unsubRequest = {
                            jsonrpc: '2.0',
                            id: 3,
                            method: 'eth_unsubscribe',
                            params: [subscriptionId]
                        };
                        ws.send(JSON.stringify(unsubRequest));
                    }, 30000);
                } else if (response.method === 'eth_subscription') {
                    eventsReceived++;
                    if (eventsReceived === 1) {
                        console.log(`   ✓ First event received`);
                    }
                } else if (response.id === 3) {
                    console.log(`   ✓ Unsubscribed successfully`);
                    ws.close();
                    resolve();
                }
            });

            ws.on('error', (error) => {
                console.log(`   ✗ Subscription test error: ${error.message}`);
                resolve();
            });

            ws.on('close', () => {
                resolve();
            });
        });
        console.log('');
    }

    async testLongRunningConnection() {
        console.log('5. Testing Long-Running Connection (2 minutes)...');
        
        return new Promise((resolve) => {
            const ws = new WebSocket(this.wsUrl);
            let pingInterval;
            let lastPong = Date.now();
            let connectionStart;
            let messageCount = 0;
            
            ws.on('open', () => {
                connectionStart = Date.now();
                console.log('   ✓ Connected');
                console.log('   → Monitoring connection stability...');
                
                // Subscribe to logs
                const subRequest = {
                    jsonrpc: '2.0',
                    id: 4,
                    method: 'eth_subscribe',
                    params: [
                        'logs',
                        {
                            address: '0x0000000000000000000000000000000000000000', // Zero address
                            fromBlock: 'latest'
                        }
                    ]
                };
                ws.send(JSON.stringify(subRequest));
                
                // Send periodic pings
                pingInterval = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.ping();
                        
                        // Check if we've received a pong recently
                        if (Date.now() - lastPong > 30000) {
                            console.log('   ⚠ No pong received in 30 seconds');
                        }
                    }
                }, 10000);
                
                // End test after 2 minutes
                setTimeout(() => {
                    clearInterval(pingInterval);
                    const duration = Date.now() - connectionStart;
                    console.log(`   → Connection maintained for ${Math.floor(duration / 1000)} seconds`);
                    console.log(`   → Received ${messageCount} messages`);
                    ws.close();
                    resolve();
                }, 120000);
            });

            ws.on('pong', () => {
                lastPong = Date.now();
            });

            ws.on('message', () => {
                messageCount++;
            });

            ws.on('error', (error) => {
                clearInterval(pingInterval);
                const duration = Date.now() - connectionStart;
                console.log(`   ✗ Connection error after ${Math.floor(duration / 1000)} seconds: ${error.message}`);
                resolve();
            });

            ws.on('close', (code, reason) => {
                clearInterval(pingInterval);
                const duration = connectionStart ? Date.now() - connectionStart : 0;
                console.log(`   → Connection closed after ${Math.floor(duration / 1000)} seconds`);
                console.log(`   → Close code: ${code}, reason: ${reason || 'none'}`);
                resolve();
            });
        });
        console.log('');
    }

    printReport() {
        console.log('\n=== DIAGNOSTIC REPORT ===');
        console.log(`Total connection attempts: ${this.stats.connectionAttempts}`);
        console.log(`Successful connections: ${this.stats.successfulConnections}`);
        console.log(`Total errors: ${this.stats.errors.length}`);
        console.log(`Total disconnects: ${this.stats.disconnects}`);
        
        if (this.stats.latencies.length > 0) {
            const avgLatency = this.stats.latencies.reduce((a, b) => a + b, 0) / this.stats.latencies.length;
            console.log(`Average connection latency: ${Math.floor(avgLatency)}ms`);
        }
        
        if (this.stats.errors.length > 0) {
            console.log('\nErrors encountered:');
            this.stats.errors.forEach((error, i) => {
                console.log(`  ${i + 1}. [${error.type}] ${error.message}`);
                if (error.code) console.log(`     Code: ${error.code}`);
                if (error.errno) console.log(`     Errno: ${error.errno}`);
            });
        }
        
        console.log('\n=== RECOMMENDATIONS ===');
        this.generateRecommendations();
    }

    generateRecommendations() {
        const errors = this.stats.errors;
        
        if (errors.some(e => e.type === 'DNS')) {
            console.log('• DNS issues detected: Check your DNS configuration and network connectivity');
        }
        
        if (errors.some(e => e.message.includes('ETIMEDOUT'))) {
            console.log('• Timeout errors: Consider increasing connection timeout or checking firewall rules');
        }
        
        if (errors.some(e => e.message.includes('ECONNREFUSED'))) {
            console.log('• Connection refused: Verify the RPC endpoint is accessible and accepting connections');
        }
        
        if (errors.some(e => e.message.includes('certificate'))) {
            console.log('• TLS/Certificate issues: Verify SSL certificates and consider using a different RPC provider');
        }
        
        if (this.stats.disconnects > this.stats.successfulConnections) {
            console.log('• High disconnect rate: Implement reconnection logic with exponential backoff');
        }
        
        if (this.stats.successfulConnections === 0) {
            console.log('• No successful connections: Check if the WebSocket URL is correct and accessible');
        }
    }
}

// Run diagnostics
if (process.argv.length < 3) {
    console.error('Usage: node diagnose_ws.js <websocket_url>');
    console.error('Example: node diagnose_ws.js wss://eth-mainnet.g.alchemy.com/v2/your-api-key');
    process.exit(1);
}

const wsUrl = process.argv[2];
const diagnostics = new WebSocketDiagnostics(wsUrl);

diagnostics.runFullDiagnostics().catch(error => {
    console.error('Diagnostic tool error:', error);
    process.exit(1);
});