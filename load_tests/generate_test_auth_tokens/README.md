node --watch --loader ts-node/esm --experimental-specifier-resolution node src



curl --url https://mainnet.infura.io/v3/7e713cef2bdb49988a13d62ed2a08280 \
-X POST \
-H "Content-Type: application/json" \
-d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'
