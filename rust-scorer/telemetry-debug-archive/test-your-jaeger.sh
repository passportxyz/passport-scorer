#!/bin/bash

echo "Testing YOUR Jaeger setup..."

echo ""
echo "1. Testing OTLP HTTP endpoint (4318):"
curl -X POST http://localhost:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{"resourceSpans":[]}' \
  -v 2>&1 | grep -E "HTTP|Connected"

echo ""
echo "2. Testing OTLP gRPC endpoint (4317):"
nc -zv localhost 4317 2>&1

echo ""
echo "3. Testing Jaeger native ports:"
nc -zv localhost 14268 2>&1
nc -zv localhost 14250 2>&1

echo ""
echo "4. Is Jaeger container running with OTLP?"
docker ps | grep jaeger

echo ""
echo "5. Check Jaeger logs for OTLP:"
docker logs jaeger 2>&1 | grep -i otlp | head -5

echo ""
echo "If OTLP isn't enabled, restart Jaeger with:"
echo "docker rm -f jaeger"
echo "docker run -d --name jaeger -e COLLECTOR_OTLP_ENABLED=true -p 16686:16686 -p 4317:4317 -p 4318:4318 jaegertracing/all-in-one:latest"