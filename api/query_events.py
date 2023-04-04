from typing import Union

from web3 import Web3
from web3.middleware import geth_poa_middleware

# Connect to a local Ethereum node or a service like Infura
w3 = Web3(
    Web3.HTTPProvider(
        "https://eth-mainnet.g.alchemy.com/v2/REPLACE_WITH_YOUR_ALCHEMY_KEY"
    )
)
w3.middleware_onion.inject(
    geth_poa_middleware, layer=0
)  # Only necessary for POA chains like Goerli, Rinkeby, etc.

user_eth_address = "0x12299d05b91b3dbb39e1f5904af61714f284e649"

# Contract address and ABI
contract_address = "0xE2Bf906f7d10F059cE65769F53fe50D8E0cC7cBe"
abi = [
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": False,
                "internalType": "uint8",
                "name": "version",
                "type": "uint8",
            }
        ],
        "name": "Initialized",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "previousOwner",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "newOwner",
                "type": "address",
            },
        ],
        "name": "OwnershipTransferred",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": False,
                "internalType": "address",
                "name": "roundAddress",
                "type": "address",
            }
        ],
        "name": "RoundContractUpdated",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "roundAddress",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "ownedBy",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "roundImplementation",
                "type": "address",
            },
        ],
        "name": "RoundCreated",
        "type": "event",
    },
    {
        "inputs": [
            {"internalType": "bytes", "name": "encodedParameters", "type": "bytes"},
            {"internalType": "address", "name": "ownedBy", "type": "address"},
        ],
        "name": "create",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "initialize",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "renounceOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "roundContract",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "newOwner", "type": "address"}],
        "name": "transferOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "newRoundContract", "type": "address"}
        ],
        "name": "updateRoundContract",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Create contract object
contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)

contract_events = contract.events.RoundCreated().create_filter(
    fromBlock=0, toBlock="latest", argument_filters={"ownedBy": user_eth_address}
)

print(contract_events.get_all_entries())


# result: [AttributeDict({'args': AttributeDict({'roundAddress': '0x28D4164c6Df015a79E1f6F7a3B1675791CDDd545', 'ownedBy': '0x12299d05B91B3Dbb39E1F5904AF61714F284e649', 'roundImplementation': '0x3e7f72DFeDF6ba1BcBFE77A94a752C529Bb4429E'}), 'event': 'RoundCreated', 'logIndex': 245, 'transactionIndex': 144, 'transactionHash': HexBytes('0x90790baaf4c89bfab7a3b8a324cbbe2c4894cd56c9eaa8ad55468dfc4dd89ed6'), 'address': '0xE2Bf906f7d10F059cE65769F53fe50D8E0cC7cBe', 'blockHash': HexBytes('0x6a3297323c781c393bbe88ef86a1ce590213a50d358c9f58ec6cbed53520881a'), 'blockNumber': 16450697})]
