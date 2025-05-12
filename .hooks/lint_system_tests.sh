#!/bin/bash

cd system_tests
for file in "$@"; do
  npx prettier --write ../${file}
done
