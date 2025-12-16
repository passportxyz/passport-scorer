# Smart Wallet Authentication - Investigation Status

## Problem Statement

We need to support Coinbase Smart Wallet (and other ERC-4337 smart wallets) for SIWE (Sign-In With Ethereum) authentication. Currently, signature verification fails for smart wallet signatures.

## Current State

**Status: WORKING - Using viem via Node.js subprocess**

### Solution

After extensive debugging, we found that Python's ERC-6492 bytecode verification (both Ambire and viem's bytecode) returns different results than viem's JavaScript implementation, even with identical bytecode.

The working solution is to call viem directly via a Node.js subprocess for ERC-6492 signature verification.

### What Works
- EOA (Externally Owned Account) signatures work fine via ecrecover
- Smart wallet signatures now verified via viem (Node.js subprocess)
- The signature IS being created and returned from the wallet
- The signature IS ERC-6492 wrapped (contains factory deployment data)

### Architecture

```
Frontend (viem/wagmi)
    |
    | Sign SIWE message with smart wallet
    v
Backend (Python/Django)
    |
    | 1. Try ecrecover (fails for smart wallets)
    | 2. Call Node.js subprocess with viem
    v
scripts/verify_erc6492.js (viem)
    |
    | verifyMessage() with ERC-6492 support
    v
Returns true/false
```

## Root Cause Analysis

### The Hash Mismatch (Expected Behavior)

When we receive a signature from Coinbase Smart Wallet:

1. **Our computed hash** (EIP-191): `b52f8b34e9bce3c577f61ae428b3b8450c5f914deb8a602ec2b3dc6e1e494305`
2. **WebAuthn challenge in signature**: `fb45f7652bef023b624e01a67e81c6a118f4d45231fe01ccc4be2681a2e48d58`

These are different because Coinbase Smart Wallet uses a **replaySafeHash** mechanism (EIP-712 wrapped). This is EXPECTED - the ERC-6492 validator handles this internally.

### Why Python Bytecode Verification Failed

We tried two bytecodes:
1. **Ambire's signature-validator** - Different bytecode, returned `0x00` (invalid)
2. **viem's exact bytecode** - Same bytecode as viem, still returned `0x00` (invalid)

The issue appears to be in how web3.py encodes the constructor parameters or handles the eth_call differently than viem. The exact cause is unknown, but the viem subprocess solution works reliably.

### Chain Verification

Smart wallet signatures must be verified on the chain the user was connected to when signing:
- Connected on Ethereum (chain 1) → Verify on chain 1 ✓
- Connected on Base (chain 8453) → Verify on chain 8453 ✓

The SIWE message's `chainId` field indicates which chain to verify on.

## Code Changes Made

### Backend (`api/ceramic_cache/api/v1.py`)

1. **Added viem verification function** `verify_signature_erc6492_viem()` - calls Node.js subprocess
2. **Fixed EIP-191 hash computation** - hash full prefixed message, not just body
3. **Multi-chain fallback** - tries specified chain first, then Base, mainnet, OP, Arb

Key function: `verify_signature_erc6492_viem()` at line ~687

### Backend (`api/scripts/verify_erc6492.js`)

New Node.js script that uses viem for ERC-6492 verification:
- Takes address, message, signature, chainId as arguments
- Returns "true" or "false" to stdout
- Uses viem's `verifyMessage()` which handles ERC-6492 automatically

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

Test page to debug signature flow (in ../project repo):
- Connect wallet via web3Modal
- Sign SIWE message (same format as main app)
- Decode the ERC-6492 signature structure
- Extract WebAuthn challenge
- Compare hashes
- Verify with viem's verifyMessage

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

## Dependencies

### Node.js (for viem verification)
```bash
cd api/scripts
npm install viem
```

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

### Test viem verification directly
```bash
cd api/scripts
node verify_erc6492.js <address> <message> <signature> <chainId>
```

## Relevant Files

### Backend
- `api/ceramic_cache/api/v1.py` - Main authentication logic, ERC-6492 verification
- `api/scripts/verify_erc6492.js` - Node.js viem verification script
- `api/scorer/settings/base.py` - Chain RPC configuration

### Frontend
- `app/pages/test-smart-wallet.tsx` - Test page for debugging (in ../project)
- `app/utils/web3.ts` - Wallet configuration
- `app/context/datastoreConnectionContext.tsx` - SIWE authentication flow

## References

- [ERC-6492 Spec](https://eips.ethereum.org/EIPS/eip-6492)
- [Coinbase Smart Wallet GitHub](https://github.com/coinbase/smart-wallet)
- [Base Docs - Signature Verification](https://docs.base.org/identity/smart-wallet/guides/signature-verification)
- [viem verifyMessage](https://viem.sh/docs/actions/public/verifyMessage)

## Git Branch

All changes are on branch: `smart-wallets-1`

## Future Improvements

1. **Pure Python solution** - Figure out why Python bytecode verification differs from viem
2. **Performance** - Node.js subprocess has ~100ms overhead; consider long-running Node process
3. **Error handling** - Better error messages for specific failure cases
