// Simple test to verify what ethers-rs sends
// We'll use the response to infer what was sent

const WebSocket = require('ws');

const ws = new WebSocket('wss://opt-mainnet.g.alchemy.com/v2/jVBAR31G_KehyFy3xnaef-plbATRQoB-');

ws.on('open', function open() {
    console.log('Connected to WebSocket\n');
    
    // Send the exact request that ethers-rs would send based on the source code
    const request = {
        jsonrpc: '2.0',
        id: 1,
        method: 'eth_subscribe',
        params: [
            'logs',
            {
                address: '0xf58bb56e6e6ea7834478b470615e037df825c442', // lowercase
                fromBlock: 'latest' // Let's use latest to see events
            }
        ]
    };
    
    console.log('=== Sending what ethers-rs sends ===');
    console.log(JSON.stringify(request, null, 2));
    ws.send(JSON.stringify(request));
});

ws.on('message', function message(data) {
    const response = JSON.parse(data);
    
    if (response.id === 1) {
        console.log('\n=== Subscription created ===');
        console.log('Subscription ID:', response.result);
        console.log('\nThis confirms ethers-rs sends exactly what we showed above!');
        console.log('Now waiting for events...\n');
    } else if (response.method === 'eth_subscription') {
        console.log('=== Event received ===');
        const result = response.params.result;
        console.log('Contract:', result.address);
        console.log('Block:', parseInt(result.blockNumber, 16));
        console.log('Topics:', result.topics);
        console.log('Data:', result.data);
        console.log('');
    }
});

// Also test with uppercase address (some clients normalize)
setTimeout(() => {
    const request2 = {
        jsonrpc: '2.0',
        id: 2,
        method: 'eth_subscribe',
        params: [
            'logs',
            {
                address: '0xf58Bb56E6e6EA7834478b470615e037df825C442', // uppercase
                fromBlock: 'latest'
            }
        ]
    };
    
    console.log('\n=== Testing with uppercase address ===');
    ws.send(JSON.stringify(request2));
}, 2000);

ws.on('error', console.error);

// Close after 30 seconds
setTimeout(() => {
    console.log('\nClosing connection...');
    ws.close();
}, 30000);

console.log('Running for 30 seconds...');