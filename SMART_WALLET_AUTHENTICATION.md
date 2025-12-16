# Smart Wallet Authentication - SOLVED

## Problem Statement

We need to support Coinbase Smart Wallet (and other ERC-4337 smart wallets) for SIWE (Sign-In With Ethereum) authentication.

## Status: FIXED ✅

Smart wallet authentication now works with **pure Python** ERC-6492 verification. No Node.js dependency required!

## Root Cause Found

The bug was in the EIP-191 hash computation. Python's `encode_defunct()` returns:
- `version = b'E'` (0x45)
- `header = b'thereum Signed Message:\n<length>'`

When concatenated, this gives `Ethereum Signed Message:\n<length><message>` - **MISSING the `\x19` prefix byte!**

The correct EIP-191 format is: `\x19Ethereum Signed Message:\n<length><message>`

### The Fix

```python
# WRONG (missing \x19):
prefixed_message = encode_defunct(text=message_text)
full_prefixed_data = prefixed_message.version + prefixed_message.header + prefixed_message.body
message_hash = Web3.keccak(full_prefixed_data)

# CORRECT (proper EIP-191):
message_bytes = message_text.encode('utf-8')
full_prefixed_data = b'\x19Ethereum Signed Message:\n' + str(len(message_bytes)).encode() + message_bytes
message_hash = Web3.keccak(full_prefixed_data)
```

With the correct hash, the pure Python bytecode verification works identically to viem.

## How It Works

```
Frontend (viem/wagmi)
    |
    | Sign SIWE message with smart wallet
    v
Backend (Python/Django)
    |
    | 1. Try ecrecover (fails for smart wallets)
    | 2. Use ERC-6492 bytecode verification (pure Python)
    v
eth_call with deployless validator bytecode
    |
    | Returns 0x01 (valid) or 0x00 (invalid)
    v
Authentication succeeds/fails
```

## Chain Verification

Smart wallet signatures must be verified on the chain where the wallet is deployed:
- Coinbase Smart Wallet is deployed on Base (chain 8453)
- Verification tries: specified chain → Base → mainnet → OP → Arb

## Files Changed

### Backend (`api/ceramic_cache/api/v1.py`)

1. **Fixed EIP-191 hash computation** (lines 975-982) - now includes `\x19` prefix
2. **Uses pure Python ERC-6492 verification** - `verify_signature_erc6492()` function
3. **Multi-chain fallback** - tries specified chain first, then common smart wallet chains


## The ERC-6492 Signature Structure

```
[factory address (32 bytes, padded)]     <- 0xca11bde05977b3631167028862be2a173976ca11 (Multicall3)
[factory calldata offset]
[inner signature offset]
[factory calldata length]
[factory calldata]                        <- Deploys smart wallet if needed
[inner signature length]
[inner signature]                         <- WebAuthn signature
[ERC-6492 magic bytes]                    <- 6492...6492 (32 bytes)
```

## Test Commands

### Test Page
```
http://localhost:3000/test-smart-wallet
```

### Verify Manually
```bash
python3 api/scripts/debug_erc6492.py <address> <message> <signature> <chainId>
```

## References

- [ERC-6492 Spec](https://eips.ethereum.org/EIPS/eip-6492)
- [Coinbase Smart Wallet](https://github.com/coinbase/smart-wallet)
- [viem verifyMessage](https://viem.sh/docs/actions/public/verifyMessage)

## Git Branch

All changes on branch: `smart-wallets-1`
