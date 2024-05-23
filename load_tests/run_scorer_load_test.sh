#!/bin/sh

# call this script like:
# - run_load_test.sh 10 1s

VIRTUAL_USERS="$1"
TEST_DURATION="$2"

# Get the current date and time in ISO 8601 format
CURRENT_DATETIME_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
RANDOM_STRING=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 8)

echo "Number of VUs : ${VIRTUAL_USERS}"
echo "Duration : ${TEST_DURATION}"

# generate the file `test_data/generated_accounts_100.json`
# generate the file `test_data/vcs/*`
cd ./test_data
pipenv run python generate_test_accounts.py
pipenv run python generate_test_vcs.py
cd ..

# generate the auth tokens ...
cd generate_test_auth_tokens
node script_backup.js
cd ..

# run the tests
k6 run -e SCORER_API_KEY="${SCORER_API_KEY}" -e SCORER_ID="${SCORER_ID}" --summary-export summary.json --out csv=k6_metrics.csv --vus "${VIRTUAL_USERS}" --duration "${TEST_DURATION}" test_scripts/scorer_api_script.js

# Upload ...
echo "Current DateTime in ISO format: $CURRENT_DATETIME_ISO"
aws s3 cp summary.json "s3://passport-load-test-reports/${CURRENT_DATETIME_ISO} ${RANDOM_STRING} summary.json"
aws s3 cp k6_metrics.csv "s3://passport-load-test-reports/${CURRENT_DATETIME_ISO} ${RANDOM_STRING} k6_metrics.csv"
