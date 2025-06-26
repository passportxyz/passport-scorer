#!/bin/bash
# Run just one test
set -e

# Run the full test script but with a specific test
export CARGO_TEST_ARGS="test_events_in_same_block"
./test-indexer.sh