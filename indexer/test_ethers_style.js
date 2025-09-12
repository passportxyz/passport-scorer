const WebSocket = require('ws');

const ws = new WebSocket('wss://opt-mainnet.g.alchemy.com/v2/jVBAR31G_KehyFy3xnaef-plbATRQoB-');

// Contract address for IdentityStaking on Optimism
const contractAddress = '0xf58Bb56E6e6EA7834478b470615e037df825C442';

ws.on('open', function open() {
    console.log('Connected to WebSocket');
    
    // This is what ethers-rs actually sends when you call .events().from_block(X).stream()
    // It doesn't pre-filter by specific event signatures - it gets ALL events from the contract
    const subscribeRequest = {
        jsonrpc: '2.0',
        id: 1,
        method: 'eth_subscribe',
        params: [
            'logs',
            {
                address: contractAddress,
                fromBlock: '0x825c620' // block 136693280 in hex
                // Note: No topics filter! Gets all events from this contract
            }
        ]
    };
    
    console.log('\n=== ACTUAL ethers-rs eth_subscribe request ===');
    console.log('This is what gets sent when you call:');
    console.log('  id_staking_contract.events().from_block(136693280).stream()');
    console.log('\nJSON-RPC Request:');
    console.log(JSON.stringify(subscribeRequest, null, 2));
    
    ws.send(JSON.stringify(subscribeRequest));
});

ws.on('message', function message(data) {
    const response = JSON.parse(data);
    
    if (response.id === 1) {
        // Subscription confirmation
        console.log('\n=== Subscription Response ===');
        console.log(JSON.stringify(response, null, 2));
        console.log('\nNow listening for ALL events from contract', contractAddress);
        console.log('Ethers-rs will filter these client-side to match your event types');
        
        // Keep alive for a bit to see if any events come through
        setTimeout(() => {
            console.log('\nClosing connection...');
            ws.close();
        }, 5000);
    } else if (response.method === 'eth_subscription') {
        // Event notification
        console.log('\n=== Event Notification ===');
        console.log(JSON.stringify(response, null, 2));
    }
});

ws.on('error', console.error);
ws.on('close', () => console.log('Connection closed'));