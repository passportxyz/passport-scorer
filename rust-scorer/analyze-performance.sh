#!/bin/bash
set -e

echo "🔥 Rust Performance Analysis Tool"
echo "================================="
echo

# Check if inferno is installed
if ! command -v inferno-flamegraph &> /dev/null; then
    echo "Installing inferno tools..."
    cargo install inferno
fi

# Clean up old traces
rm -f tracing.folded tracing-flamegraph.svg tracing-flamechart.svg

echo "1. Starting server with flame tracing enabled..."
echo "   - Normal JSON logs still go to stdout"
echo "   - Flame data goes to ./tracing.folded"
echo

# Start the server with FLAME=1 to enable flame tracing
FLAME=1 RUST_LOG=info DATABASE_URL="${DATABASE_URL:-postgresql://localhost/test}" \
    cargo run --release --bin passport-scorer &
SERVER_PID=$!

echo "Server PID: $SERVER_PID"
echo

# Wait for server to start
sleep 3

echo "2. Making test requests..."
# Make some test requests to generate traces
for i in {1..3}; do
    echo "   Request $i..."
    curl -s -X GET "http://localhost:3003/v2/stamps/4/score/0x96db2c6d93a8a12089f7a6eda5464e967308aded" \
        -H "X-API-Key: test_key" > /dev/null 2>&1 || true
    sleep 1
done

echo
echo "3. Stopping server..."
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

echo
echo "4. Analyzing traces..."

if [ -f tracing.folded ]; then
    # Count spans
    SPAN_COUNT=$(wc -l < tracing.folded)
    echo "   Generated $SPAN_COUNT span entries"
    
    # Show top 10 stacks by time
    echo
    echo "   Top 10 stacks by total time:"
    sort -t' ' -k2 -nr tracing.folded | head -10 | while read stack time; do
        printf "   %8d µs  %s\n" "$time" "$stack"
    done
    
    echo
    echo "5. Generating visualizations..."
    
    # Generate flame graph (aggregated view)
    cat tracing.folded | inferno-flamegraph > tracing-flamegraph.svg
    echo "   ✅ Flame graph: tracing-flamegraph.svg"
    
    # Generate flame chart (time-ordered view)
    cat tracing.folded | inferno-flamegraph --flamechart > tracing-flamechart.svg
    echo "   ✅ Flame chart: tracing-flamechart.svg"
    
    echo
    echo "📊 Analysis complete!"
    echo "   - Open tracing-flamegraph.svg in a browser to explore the flame graph"
    echo "   - Open tracing-flamechart.svg to see time-ordered execution"
    echo
    echo "Tips:"
    echo "   - Flame graph: Width = time spent, Height = call stack depth"
    echo "   - Look for wide bars (time consuming operations)"
    echo "   - In our case, look for 'pbkdf2_computation' - should be very wide!"
else
    echo "   ❌ No tracing.folded file found - flame tracing may not be working"
fi