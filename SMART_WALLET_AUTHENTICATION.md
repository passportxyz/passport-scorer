# Smart Wallet Authentication - Investigation Status

## Problem Statement

We need to support Coinbase Smart Wallet (and other ERC-4337 smart wallets) for SIWE (Sign-In With Ethereum) authentication. Currently, signature verification fails for smart wallet signatures.

## Current State

**Status: BLOCKED - Hash mismatch between what we compute and what the wallet signs**

### What Works
- EOA (Externally Owned Account) signatures work fine
- The signature IS being created and returned from the wallet
- The signature IS ERC-6492 wrapped (contains factory deployment data)

### What Doesn't Work
- ERC-6492 signature verification returns `false` on all chains tested
- The WebAuthn challenge in the signature doesn't match our computed message hash

## Root Cause Analysis

### The Hash Mismatch Problem

When we receive a signature from Coinbase Smart Wallet:

1. **Our computed hash** (EIP-191): `2442c92e4fcf39ae3295b52cb30bde2534e3d99789bf0040213df854634e0dc0`
2. **WebAuthn challenge in signature**: `80c9033cbf8831c30369f2ed8f26dcb8bbd6aad8e62f7f9a9fb9fbbf4e5a200b`

These are completely different! The wallet is signing something else.

### Why This Happens

Coinbase Smart Wallet uses a **replaySafeHash** mechanism (from their ERC1271.sol):

```solidity
function replaySafeHash(bytes32 hash) public view returns (bytes32) {
    return _eip712Hash(hash);
}

// Which computes:
keccak256("\x19\x01" || domainSeparator() || hashStruct(hash))
```

The `domainSeparator` includes:
- Contract name: "Coinbase Smart Wallet"
- Version: "1"
- **Chain ID** (critical!)
- Wallet contract address

### The Chain ID Problem

The SIWE message contains a `chainId` field (e.g., `chainId: 1` for mainnet). But the wallet's domain separator uses the chain where the **wallet contract** is deployed (e.g., Base = 8453).

So if:
- SIWE message has `chainId: 1`
- Wallet is on Base (`chainId: 8453`)
- The `replaySafeHash` computation uses Base's chain ID
- Our verification uses mainnet's chain ID
- **Hashes don't match!**

### Additional Complexity

The ERC-6492 validator should handle this by:
1. Deploying the wallet contract (via factory calldata in signature)
2. Calling `wallet.isValidSignature(hash, innerSignature)`
3. The wallet internally computes `replaySafeHash(hash)` and verifies

But verification still fails, possibly because:
- The wallet isn't getting deployed correctly in the `eth_call` simulation
- The domain separator chain ID doesn't match
- Something else in the WebAuthn/passkey verification is failing

## Code Changes Made

### Backend (`api/ceramic_cache/api/v1.py`)

1. **Added ERC-6492 verification** with multi-chain fallback
2. **Switched to deployless verification** using Ambire's bytecode (doesn't require pre-deployed validator contract)
3. **Added testnet chain support** for development

Key function: `verify_signature_erc6492()` at line ~687

### Backend (`api/scorer/settings/base.py`)

Added testnet chain IDs to `ALCHEMY_CHAIN_NETWORKS`:
```python
ALCHEMY_CHAIN_NETWORKS = {
    # Mainnets
    1: "eth-mainnet",
    8453: "base-mainnet",
    # ... etc
    # Testnets
    11155111: "eth-sepolia",
    11155420: "opt-sepolia",
    84532: "base-sepolia",
    421614: "arb-sepolia",
}
```

### Frontend Test Page (`app/pages/test-smart-wallet.tsx`)

Created a test page to debug signature flow:
- Connect wallet via web3Modal
- Sign a plain message
- Decode the ERC-6492 signature structure
- Extract WebAuthn challenge
- Compare hashes
- Try Viem's `verifyMessage`

## Signature Structure (ERC-6492)

```
[factory address (32 bytes, padded)]
[factory calldata offset]
[inner signature offset]
[factory calldata length]
[factory calldata (calls Multicall3 -> CoinbaseSmartWalletFactory.createAccount)]
[inner signature length]
[inner signature (WebAuthn signature with clientDataJSON)]
[ERC-6492 magic bytes: 6492...6492]
```

### Key Addresses Found in Signature

- **Multicall3**: `0xca11bde05977b3631167028862be2a173976ca11` (factory in ERC-6492)
- **CoinbaseSmartWalletFactory**: `0xba5ed110efdba3d005bfc882d75358acbbb85842` (called via Multicall3)

## What Needs to Be Done

### Option 1: Fix the Hash Computation

Figure out exactly what hash the frontend is sending to the wallet and ensure our backend computes the same hash for verification.

Steps:
1. Add logging in frontend to capture the exact bytes being signed
2. Trace through wagmi/viem to see what transformation happens
3. Match that transformation in backend verification

### Option 2: Use Viem's verifyMessage on Backend

Viem's `verifyMessage` supposedly handles ERC-6492 automatically. We could:
1. Create a simple Node.js verification service
2. Or port Viem's verification logic to Python

### Option 3: Ask Coinbase/Base for Guidance

Their docs recommend using Viem but don't explain the hash transformation. May need to:
1. Check their Discord/GitHub issues
2. Look at working implementations (if any exist in Python)

## Test Commands

### Run Backend
```bash
cd /workspace/passport-scorer
docker compose up
```

### Run Frontend
```bash
cd /workspace/project/app
yarn start
```

### Test Page URL
```
http://localhost:3000/test-smart-wallet
```

## Relevant Files

### Backend
- `api/ceramic_cache/api/v1.py` - Main authentication logic, ERC-6492 verification
- `api/scorer/settings/base.py` - Chain RPC configuration

### Frontend
- `app/pages/test-smart-wallet.tsx` - Test page for debugging
- `app/utils/web3.ts` - Wallet configuration
- `app/context/ceramicContext.tsx` - SIWE authentication flow

## References

- [ERC-6492 Spec](https://eips.ethereum.org/EIPS/eip-6492)
- [Coinbase Smart Wallet GitHub](https://github.com/coinbase/smart-wallet)
- [Base Docs - Signature Verification](https://docs.base.org/identity/smart-wallet/guides/signature-verification)
- [Ambire Signature Validator](https://github.com/AmbireTech/signature-validator)

## Git Branch

All changes are on branch: `smart-wallets-1`

Recent commits:
- `fix(auth): use deployless ERC-6492 validation for smart wallets`
- `fix(auth): move message_hash computation before debug logging`
- `fix(auth): improve smart wallet debug logging to info level`
- `fix(auth): add multi-chain ERC-6492 verification fallback for smart wallets`
