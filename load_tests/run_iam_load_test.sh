#!/bin/sh

# call this script like:
#   - run_load_test.sh 10 1s

cd ./test_data
pipenv run python generate_test_accounts.py
cd ..

# generate the file `test_data/vcs/*`
cd generate_test_auth_tokens
node script_backup.js
cd ..

echo "Number of VUs :" $1
echo "Duration      :" $2
k6 run --vus $1 --duration $2 --out csv=k6_metrics.csv test_scripts/iam_script.js
