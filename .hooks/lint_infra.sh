#!/bin/bash

cd infra
for file in "$@"; do
  npx prettier --write ../${file}
done
