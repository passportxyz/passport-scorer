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
SCORER_ID = 335  # Change this to your scorer ID
ENDPOINT = "https://api.scorer.gitcoin.co"

# Test addresses - replace with your own
TEST_ADDRESSES = [
    "0x5B79f9768Df200DF2e2c6F2d66Db37B8bF40ff23",
    "0x433DCa92Fa20c16bCD4d19C4f395210513E6b61f",
    "0xE4553b743E74dA3424Ac51f8C1E586fd43aE226F",
    "0x3829c53Fc227aFF5dB0Bf99c50FBBb372eFb5d2e",
    "0xC7aCFe1C11d43f23073E5bD0eb37D3D5bda86331",
    # Add more addresses here
]


def call_scorer(address: str, use_rust: bool = False) -> Dict:
    """Call either Python or Rust scorer endpoint"""
    url = f"{ENDPOINT}/v2/stamps/{SCORER_ID}/score/{address}"

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    if use_rust:
        headers["X-Use-Rust-Scorer"] = "true"

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def compare_scores(py: Dict, rust: Dict) -> str:
    """Simple comparison of scores"""
    if "error" in py:
        return f"❌ Python error: {py['error']}"
    if "error" in rust:
        return f"❌ Rust error: {rust['error']}"

    py_score = py.get("score", "?")
    rust_score = rust.get("score", "?")

    if py_score == rust_score:
        return f"✅ Match: {py_score}"
    else:
        return f"⚠️  Mismatch: Python={py_score}, Rust={rust_score}"


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
        results.append({
            "address": address,
            "python": py_resp,
            "rust": rust_resp,
            "comparison": result
        })

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