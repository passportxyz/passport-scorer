# Generate test data

## generate the file `test_data/generated_accounts_100.json`

- `cd ./test_data`
- make sure you have the pipenv environment create: `pipenv install`
- enter the pipenv: `pipenv shell`
- create the `.env` file, and configure the mnemonic (see the `.env-example`)
  - tip: stick to the default values where these are specified in `.env-example`
- adjust the `generate_test_accounts.py`
- run `python generate_test_accounts.py`

## generate the file `test_data/vcs/*`

- make sure you create the folder `test_data/vcs`
- run `python generate_test_vcs.py`
- the results will be written to individual files in the `test_data/vcs` folder

## generate `generate_test_auth_tokens/user-tokens.json`

- `cd generate_test_auth_tokens`
- run `npm install`
- make sure to set the environent variables:

```bash
export MNEMONIC='chief loud snack trend chief net field husband vote message decide replace'
export ALCHEMY_API_KEY='<YOUR API KEY>'
```

- run `node script_backup.js`
- the output will be written to `generate_test_auth_tokens/user-tokens.json`

Adjust the `script.js`:

- make sure to set a valid scorer id: `const scorerId = 24;`
- make sure to set a valid api key: `const apiKey = "...";`
- make sure you remove the API limit for the API key

# Running

## Locally

Run locally like:
`k6 run -e SCORER_API_KEY=<your API key> -e SCORER_ID=<your scorer id> --vus 10 --duration 30s script.js`
or
`k6 run -e SCORER_API_KEY=<your API key> -e SCORER_ID=<your scorer id> script.js`

## In cloud

First make sure to set the environment variables: https://k6.io/docs/cloud/manage/environment-variables/

Then run in cloud like:
`k6 cloud --vus 1000 --duration 30m script.js`
