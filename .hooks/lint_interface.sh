#!/bin/bash

cd interface
for file in "$@"; do
  npx prettier --write ../${file}
done
