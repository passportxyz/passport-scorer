#!/usr/bin/env python3
"""
Debug script to compare Python vs viem ERC-6492 verification byte-by-byte.
"""

import subprocess
import os
from web3 import Web3
from eth_account.messages import encode_defunct

# Test data - REPLACE THESE with actual values from a smart wallet signing
TEST_ADDRESS = "0x9e068046a15E776F734c2733b73F9849D08Cf844"
TEST_MESSAGE = """localhost wants you to sign in with your Ethereum account:
0x9e068046a15E776F734c2733b73F9849D08Cf844

Sign in to Human Passport

URI: http://localhost:3000
Version: 1
Chain ID: 1
Nonce: abc123
Issued At: 2025-01-01T00:00:00.000Z"""

# ERC-6492 Signature Validator bytecode from viem
UNIVERSAL_VALIDATOR_BYTECODE = bytes.fromhex(
    "608060405234801561001057600080fd5b5060405161069438038061069483398101604081905261002f9161051e565b600061003c848484610048565b9050806000526001601ff35b60007f64926492649264926492649264926492649264926492649264926492649264926100748361040c565b036101e7576000606080848060200190518101906100929190610577565b60405192955090935091506000906001600160a01b038516906100b69085906105dd565b6000604051808303816000865af19150503d80600081146100f3576040519150601f19603f3d011682016040523d82523d6000602084013e6100f8565b606091505b50509050876001600160a01b03163b60000361016057806101605760405162461bcd60e51b815260206004820152601e60248201527f5369676e617475726556616c696461746f723a206465706c6f796d656e74000060448201526064015b60405180910390fd5b604051630b135d3f60e11b808252906001600160a01b038a1690631626ba7e90610190908b9087906004016105f9565b602060405180830381865afa1580156101ad573d6000803e3d6000fd5b505050506040513d601f19601f820116820180604052508101906101d19190610633565b6001600160e01b03191614945050505050610405565b6001600160a01b0384163b1561027a57604051630b135d3f60e11b808252906001600160a01b03861690631626ba7e9061022790879087906004016105f9565b602060405180830381865afa158015610244573d6000803e3d6000fd5b505050506040513d601f19601f820116820180604052508101906102689190610633565b6001600160e01b031916149050610405565b81516041146102df5760405162461bcd60e51b815260206004820152603a602482015260008051602061067483398151915260448201527f3a20696e76616c6964207369676e6174757265206c656e6774680000000000006064820152608401610157565b6102e7610425565b5060208201516040808401518451859392600091859190811061030c5761030c61065d565b016020015160f81c9050601b811480159061032b57508060ff16601c14155b1561038c5760405162461bcd60e51b815260206004820152603b602482015260008051602061067483398151915260448201527f3a20696e76616c6964207369676e617475726520762076616c756500000000006064820152608401610157565b60408051600081526020810180835289905260ff83169181019190915260608101849052608081018390526001600160a01b0389169060019060a0016020604051602081039080840390855afa1580156103ea573d6000803e3d6000fd5b505050602060405103516001600160a01b0316149450505050505b9392505050565b600060208251101561041d57600080fd5b508051015190565b60405180606001604052806003906020820280368337509192915050565b6001600160a01b038116811461045857600080fd5b50565b634e487b7160e01b600052604160045260246000fd5b60005b8381101561048c578181015183820152602001610474565b50506000910152565b600082601f8301126104a657600080fd5b81516001600160401b038111156104bf576104bf61045b565b604051601f8201601f19908116603f011681016001600160401b03811182821017156104ed576104ed61045b565b60405281815283820160200185101561050557600080fd5b610516826020830160208701610471565b949350505050565b60008060006060848603121561053357600080fd5b835161053e81610443565b6020850151604086015191945092506001600160401b0381111561056157600080fd5b61056d86828701610495565b9150509250925092565b60008060006060848603121561058c57600080fd5b835161059781610443565b60208501519093506001600160401b038111156105b357600080fd5b6105bf86828701610495565b604086015190935090506001600160401b0381111561056157600080fd5b600082516105ef818460208701610471565b9190910192915050565b828152604060208201526000825180604084015261061e816060850160208701610471565b601f01601f1916919091016060019392505050565b60006020828403121561064557600080fd5b81516001600160e01b03198116811461040557600080fd5b634e487b7160e01b600052603260045260246000fdfe5369676e617475726556616c696461746f72237265636f7665725369676e6572"
)

def get_rpc_url(chain_id: int) -> str:
    """Get Alchemy RPC URL for chain"""
    networks = {
        1: "eth-mainnet",
        8453: "base-mainnet",
    }
    network = networks.get(chain_id, "eth-mainnet")
    api_key = os.environ.get("ALCHEMY_API_KEY", "demo")
    return f"https://{network}.g.alchemy.com/v2/{api_key}"


def debug_python_approach(address: str, message: str, signature: str, chain_id: int = 1):
    """Debug the Python bytecode approach"""
    print("\n=== PYTHON BYTECODE APPROACH ===")

    w3 = Web3(Web3.HTTPProvider(get_rpc_url(chain_id), request_kwargs={"timeout": 10}))
    checksum_address = Web3.to_checksum_address(address)

    # Compute hash (EIP-191)
    prefixed_message = encode_defunct(text=message)
    full_prefixed_data = prefixed_message.version + prefixed_message.header + prefixed_message.body
    message_hash = Web3.keccak(full_prefixed_data)

    print(f"Message text length: {len(message)}")
    print(f"EIP-191 prefixed data: {full_prefixed_data[:50].hex()}...")
    print(f"Message hash: {message_hash.hex()}")

    # Prepare signature
    sig_bytes = bytes.fromhex(signature.replace("0x", ""))
    print(f"Signature length: {len(sig_bytes)} bytes")

    # Check ERC-6492 magic
    ERC6492_MAGIC = bytes.fromhex("6492649264926492649264926492649264926492649264926492649264926492")
    is_6492 = sig_bytes[-32:] == ERC6492_MAGIC if len(sig_bytes) >= 32 else False
    print(f"Is ERC-6492 wrapped: {is_6492}")

    # ABI encode
    encoded_params = w3.codec.encode(
        ['address', 'bytes32', 'bytes'],
        [checksum_address, message_hash, sig_bytes]
    )
    print(f"Encoded params length: {len(encoded_params)} bytes")
    print(f"Encoded params (first 100 bytes): {encoded_params[:100].hex()}")

    # Full calldata
    call_data = UNIVERSAL_VALIDATOR_BYTECODE + encoded_params
    print(f"Total calldata length: {len(call_data)} bytes")
    print(f"Bytecode length: {len(UNIVERSAL_VALIDATOR_BYTECODE)} bytes")

    # Make the call
    try:
        result = w3.eth.call({'data': call_data})
        print(f"eth_call result (raw): {result}")
        print(f"eth_call result (hex): {result.hex()}")
        print(f"eth_call result length: {len(result)} bytes")

        # Check different interpretations
        print(f"result == b'\\x01': {result == b'\\x01'}")
        print(f"result == b'\\x00': {result == b'\\x00'}")
        print(f"len(result) == 1: {len(result) == 1}")
        if len(result) >= 1:
            print(f"result[0]: {result[0]}")
            print(f"result[0] == 1: {result[0] == 1}")
    except Exception as e:
        print(f"eth_call FAILED: {e}")


def debug_viem_approach(address: str, message: str, signature: str, chain_id: int = 1):
    """Debug the viem approach via Node.js"""
    print("\n=== VIEM (NODE.JS) APPROACH ===")

    script_path = os.path.join(os.path.dirname(__file__), 'verify_erc6492.js')

    try:
        result = subprocess.run(
            ['node', script_path, address, message, signature, str(chain_id)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(script_path)
        )
        print(f"stdout: '{result.stdout.strip()}'")
        print(f"stderr: '{result.stderr.strip()}'")
        print(f"return code: {result.returncode}")
        is_valid = result.stdout.strip().lower() == 'true'
        print(f"Interpreted as valid: {is_valid}")
    except Exception as e:
        print(f"Node.js call FAILED: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 4:
        addr = sys.argv[1]
        msg = sys.argv[2]
        sig = sys.argv[3]
        chain = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    else:
        print("Usage: python debug_erc6492.py <address> <message> <signature> [chainId]")
        print("\nUsing test values (will fail without real signature)...")
        addr = TEST_ADDRESS
        msg = TEST_MESSAGE
        sig = "0x" + "00" * 65  # Dummy signature
        chain = 1

    debug_python_approach(addr, msg, sig, chain)
    debug_viem_approach(addr, msg, sig, chain)
