// This simulates EXACTLY what ethers-rs does based on the source code analysis
const WebSocket = require('ws');

const ws = new WebSocket('wss://opt-mainnet.g.alchemy.com/v2/jVBAR31G_KehyFy3xnaef-plbATRQoB-');

ws.on('open', async function open() {
    console.log('Connected to WebSocket\n');
    
    // First get the current block number (like your Rust code does)
    const blockRequest = {
        jsonrpc: '2.0',
        id: 1,
        method: 'eth_blockNumber',
        params: []
    };
    
    console.log('1. Getting current block (like staking_indexer.rs line 164)');
    ws.send(JSON.stringify(blockRequest));
});

let currentBlockHex;

ws.on('message', function message(data) {
    const response = JSON.parse(data);
    
    if (response.id === 1) {
        // Block number response
        currentBlockHex = response.result;
        const currentBlock = parseInt(currentBlockHex, 16);
        console.log(`   Current block: ${currentBlock} (0x${currentBlockHex})\n`);
        
        // Now subscribe exactly like ethers-rs does
        const subscribeRequest = {
            jsonrpc: '2.0',
            id: 2,
            method: 'eth_subscribe',
            params: [
                'logs',
                {
                    // ethers-rs normalizes addresses to lowercase
                    address: '0xf58bb56e6e6ea7834478b470615e037df825c442',
                    fromBlock: currentBlockHex
                }
            ]
        };
        
        console.log('2. This is the EXACT JSON-RPC request sent by:');
        console.log('   id_staking_contract.events().from_block(from_block).stream()');
        console.log('   (staking_indexer.rs lines 236-238)\n');
        console.log(JSON.stringify(subscribeRequest, null, 2));
        
        ws.send(JSON.stringify(subscribeRequest));
        
    } else if (response.id === 2) {
        console.log('\n3. Subscription created successfully!');
        console.log(`   Subscription ID: ${response.result}`);
        console.log('\n   ethers-rs now filters events client-side to match:');
        console.log('   - SelfStakeFilter');
        console.log('   - CommunityStakeFilter');
        console.log('   - SelfStakeWithdrawnFilter');
        console.log('   - CommunityStakeWithdrawnFilter');
        console.log('   - SlashFilter');
        console.log('   - ReleaseFilter\n');
        console.log('   Waiting for events...');
        
    } else if (response.method === 'eth_subscription') {
        // Event notification - ethers-rs would parse this
        console.log('\n4. Raw event received (ethers-rs parses this):');
        const log = response.params.result;
        console.log(`   Block: ${parseInt(log.blockNumber, 16)}`);
        console.log(`   Event signature: ${log.topics[0]}`);
        
        // Show which event type this would be
        const eventSignatures = {
            '0x2d908861cf6c966453abf86f6d9b296b9e70bd879a0d33055b3d34d8aadf99b0': 'SelfStake',
            '0x6e7191d5333beaa8a6f056a2e8ea8a6c5c0b197f1b9af998e9c7a29e4e1e13c5': 'CommunityStake',
            '0xbac378620b3ba4a1db90762dd1b33b1097b7c30a3c93e3ad079ab1c835db9c5e': 'SelfStakeWithdrawn',
            '0xfd39efe211b8ed688f8e136e38d706bb5d02b7de86b4b08e8b7de6d90b3a37f6': 'CommunityStakeWithdrawn',
            '0xb9416604e60e3c96b076d1b8b981c835dcf6fece8c5fb6b7b9c4c0bf1b60e6f0': 'Slash',
            '0x963f3882f46e14f23e72994d5589d0c8ebdeed079f7fb4ddab1fab5f86b5bb81': 'Release'
        };
        
        const eventType = eventSignatures[log.topics[0]] || 'Unknown';
        console.log(`   Event type: ${eventType}`);
    }
});

ws.on('error', console.error);

// Run for 20 seconds
setTimeout(() => {
    console.log('\nClosing connection...');
    ws.close();
}, 20000);