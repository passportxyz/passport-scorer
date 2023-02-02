
# Test
With curl to node:
```bash
curl -X POST http://localhost:80/verify \
   -H 'Content-Type: application/json' \
   -d @test.json
```

With curl to api:
```bash
curl -X POST http://localhost:8000/ceramic-cache/authenticate \
   -H 'Content-Type: application/json' \
   -d @test.json
```
