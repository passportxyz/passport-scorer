#!/usr/bin/env python3
"""
Simple comparison script - no database required
Just provide addresses to test
"""

import json
import os
import requests
from typing import Dict, List

# Configuration
API_KEY = os.environ.get("API_KEY", "")  # Your API key
SCORER_ID = 5976  # Change this to your scorer ID
ENDPOINT = "https://api.passport.xyz"

# Test addresses - replace with your own
TEST_ADDRESSES = [
    "0xfdccfbf37340e65982f77b2a0ac5472e61bb259b",
    "0x73fdb219090ca5cafc9a4c94d158b626e4ea249e",
    "0x446dc6a6f19ea9e135777c9e1bcc5e2eae9cc988",
    "0x96DB2c6D93A8a12089f7a6EdA5464e967308AdEd",
]


def call_scorer(address: str, use_rust: bool = False) -> Dict:
    """Call either Python or Rust scorer endpoint"""
    url = f"{ENDPOINT}/v2/stamps/{SCORER_ID}/score/{address}"

    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

    if use_rust:
        headers["X-Use-Rust-Scorer"] = "true"

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def normalize_for_comparison(obj: Dict) -> Dict:
    """Remove timestamps and normalize for comparison"""
    normalized = obj.copy()
    # Remove timestamp fields that will naturally differ
    normalized.pop("last_score_timestamp", None)
    return normalized


def compare_scores(py: Dict, rust: Dict) -> str:
    """Compare entire response objects"""
    if "error" in py and py["error"] is not None:
        return f"❌ Python error: {py['error']}"
    if "error" in rust and rust["error"] is not None:
        return f"❌ Rust error: {rust['error']}"

    # Normalize both responses
    py_normalized = normalize_for_comparison(py)
    rust_normalized = normalize_for_comparison(rust)

    if py_normalized == rust_normalized:
        return f"✅ Match: score={py.get('score', '?')}"
    else:
        # Find what's different
        all_keys = set(py_normalized.keys()) | set(rust_normalized.keys())
        diffs = []
        for key in sorted(all_keys):
            py_val = py_normalized.get(key)
            rust_val = rust_normalized.get(key)
            if py_val != rust_val:
                diffs.append(f"{key}")

        return f"⚠️  Mismatch in: {', '.join(diffs)}"


def main():
    if not API_KEY:
        print("ERROR: Please set API_KEY environment variable")
        print("export API_KEY=your-api-key-here")
        return

    print(f"Testing {len(TEST_ADDRESSES)} addresses...")
    print(f"Scorer ID: {SCORER_ID}")
    print(f"Endpoint: {ENDPOINT}")
    print("-" * 60)

    results = []
    matches = 0
    mismatches = 0

    for i, address in enumerate(TEST_ADDRESSES, 1):
        print(f"\n[{i}/{len(TEST_ADDRESSES)}] {address}")

        # Call both endpoints
        py_resp = call_scorer(address, use_rust=False)
        rust_resp = call_scorer(address, use_rust=True)

        # Compare
        result = compare_scores(py_resp, rust_resp)
        print(f"  {result}")

        # Track stats
        if "✅" in result:
            matches += 1
        elif "⚠️" in result:
            mismatches += 1

            # Show details for mismatches
            print("\n  Python response:")
            for key in ["score", "passing_score", "threshold"]:
                if key in py_resp:
                    print(f"    {key}: {py_resp[key]}")

            print("\n  Rust response:")
            for key in ["score", "passing_score", "threshold"]:
                if key in rust_resp:
                    print(f"    {key}: {rust_resp[key]}")

            # Show stamp differences
            if "stamps" in py_resp and "stamps" in rust_resp:
                py_stamps = set(py_resp["stamps"].keys())
                rust_stamps = set(rust_resp["stamps"].keys())

                only_python = py_stamps - rust_stamps
                only_rust = rust_stamps - py_stamps

                if only_python:
                    print(f"\n  Stamps only in Python: {list(only_python)[:5]}")
                if only_rust:
                    print(f"\n  Stamps only in Rust: {list(only_rust)[:5]}")

        # Store for later analysis
        results.append(
            {
                "address": address,
                "python": py_resp,
                "rust": rust_resp,
                "comparison": result,
            }
        )

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Matches: {matches}/{len(TEST_ADDRESSES)}")
    print(f"⚠️  Mismatches: {mismatches}/{len(TEST_ADDRESSES)}")

    # Save results
    with open("quick_compare_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nDetailed results saved to quick_compare_results.json")


if __name__ == "__main__":
    main()
