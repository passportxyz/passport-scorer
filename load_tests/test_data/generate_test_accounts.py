import json

from dotenv import dotenv_values
from web3 import Web3

env_config = dotenv_values(".env")

mnemonic = env_config.get("MNEMONIC")
num_accounts = int(env_config.get("NUM_ACCOUNTS", 100))


w3 = Web3()

w3.eth.account.enable_unaudited_hdwallet_features()

account_list = []


for i in range(num_accounts):
    print(f"Generating account: {i}/{num_accounts}")
    acc = w3.eth.account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{i}")
    account_list.append(acc.address)

output_file = f"generated_accounts_{num_accounts}.json"

with open(output_file, "w") as f:
    f.write(json.dumps(account_list))

print(f"Results have been writen to '{output_file}'")
