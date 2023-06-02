
# Generate test data

## generate the file `test_data/generated_accounts_100.json`

- `cd ./test_data`
- make sure you have the pipenv environment create: `pipenv install`
- enter the pipenv: `pipenv shell`
- create the `.env` file, and configure the mnemonic (see the `.env-example`)
- adjust the `generate_test_accounts.py`
- run `python generate_test_accounts.py`

## generate the file `test_data/vcs/*`

- make sure you create the folder `test_data/vcs`
- run `python generate_test_vcs.py`
- the results will be written to individual files in the `test_data/vcs` folder

## generate `generate_test_auth_tokens/user-tokens.json`

- cd `generate_test_auth_tokens`
- run `npm install`
- run `node script_backup.js`
- the output will be written to `generate_test_auth_tokens/user-tokens.json`

Adjust the `script.js`:
- make sure to set a valid scorer id: `const scorerId = 24;`
- make sure to set a valid api key: `const apiKey = "...";`
- make sure you rmeove the API limit for the API key

# Running

## Locally

Run on like like:
`k6 run --vus 10 --duration 30s script.js`
or
`k6 run script.js`

## In cloud
Run in cloud like:

`k6 cloud --vus 1000 --duration 30m script.js`
