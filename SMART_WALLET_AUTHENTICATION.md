# Smart Wallet Authentication

## Overview

Smart wallet (ERC-4337) authentication for SIWE (Sign-In With Ethereum) is supported via ERC-6492 signature verification.

## How It Works

```
Frontend (viem/wagmi)
    |
    | Sign SIWE message (always chainId: 1)
    v
Backend (Python/Django)
    |
    | 1. Try ecrecover first (fast, local - works for EOAs)
    | 2. Fallback to ERC-6492 on mainnet (for smart wallets)
    v
Authentication succeeds/fails
```

### Why Mainnet Only?

Smart wallet factories (Coinbase, Safe, Kernel, etc.) are deployed on 100+ chains including mainnet. The ERC-6492 "deployless" validator bytecode works via `eth_call` on any EVM chain. Since we always use `chainId: 1` in SIWE messages and all major smart wallet factories are on mainnet, we only need to verify there.

## Technical Details

### EIP-191 Hash (Critical)

```python
# Correct EIP-191 format: \x19Ethereum Signed Message:\n<length><message>
message_bytes = message_text.encode('utf-8')
full_prefixed_data = b'\x19Ethereum Signed Message:\n' + str(len(message_bytes)).encode() + message_bytes
message_hash = Web3.keccak(full_prefixed_data)
```

### ERC-6492 Verification

Uses viem's Universal Signature Validator bytecode via deployless `eth_call` (no pre-deployed contract needed). Handles:
- EOA signatures (ecrecover)
- Deployed smart wallet signatures (EIP-1271)
- Undeployed/counterfactual smart wallet signatures (ERC-6492)

## References

- [ERC-6492 Spec](https://eips.ethereum.org/EIPS/eip-6492)
- [Coinbase Smart Wallet](https://github.com/coinbase/smart-wallet)
- [viem verifyMessage](https://viem.sh/docs/actions/public/verifyMessage)
