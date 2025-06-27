#!/bin/bash
# Run just one test
set -e

# Run the full test script but with a specific test
export CARGO_TEST_ARGS="test_multiple_withdraw_events"
./test-indexer.sh