#!/bin/sh

# call this script like:
#   - run_load_test.sh 10 1s

# generate the file `test_data/generated_accounts_100.json`
cd ./test_data
pipenv run python generate_test_accounts.py
cd ..

# generate the file `test_data/vcs/*`
cd generate_test_auth_tokens
node script_backup.js
cd ..

# run the tests
echo "Number of VUs :" $1
echo "Duration      :" $2
k6 run -e SCORER_API_KEY=${SCORER_API_KEY} -e SCORER_ID=${SCORER_ID} --summary-export summary.json --out csv=k6_metrics.csv --vus $1 --duration $2 test_scripts/scorer_api_script.js
