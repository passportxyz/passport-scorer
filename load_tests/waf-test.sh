#!/bin/bash
for i in {1..101}
do
   echo "Request $i"
   curl -X 'GET' 'https://api.staging.scorer.gitcoin.co/registry/score/14/0x0636F974D29d947d4946b2091d769ec6D2d415DE' -H 'accept: application/json' -H 'X-API-Key: 9jwWhvM3.7KZEzXNCEV9TWGCudUd0wl7mlSKeNVYC' &

   # Limit to 20 concurrent requests
   if (( $(($i % 20)) == 0 )) ; then
     wait # Wait for all parallel jobs to finish
   fi
done

wait # Wait for any remaining jobs to finish
