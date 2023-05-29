import json

from dotenv import dotenv_values
from web3 import Web3

env_config = dotenv_values(".env")

JWK = env_config("JWK")
mnemonic = env_config("MNEMONIC")


w3 = Web3()

w3.eth.account.enable_unaudited_hdwallet_features()

account_list = []

num_accounts = 1000000

for i in range(num_accounts):
    print(f"Generating account: {i}/{num_accounts}")
    acc = w3.eth.account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{i}")
    account_list.append(acc.address)


with open("generated_accounts.json", "w") as f:
    f.write(json.dumps(account_list))
