#!/usr/bin/env python3
"""
Test script to understand djangorestframework-api-key hashing
"""
import hashlib

def hash_api_key(key: str) -> str:
    """
    Replicate the djangorestframework-api-key v2 hashing
    Format: sha512$$<hex_hash>
    """
    # SHA512 hash of the key
    hash_obj = hashlib.sha512(key.encode())
    hex_hash = hash_obj.hexdigest()
    
    # Format as stored in database
    return f"sha512$${hex_hash}"

def extract_prefix(key: str) -> str:
    """Extract the 8-character prefix for database lookup"""
    return key[:8] if len(key) >= 8 else key

# Test with sample keys
test_keys = [
    "abcd1234.secretkeypart",
    "test1234.anothersecretkey",
    "demo9876.verysecretkey"
]

print("Python API Key Hashing Test")
print("=" * 50)

for key in test_keys:
    prefix = extract_prefix(key)
    hashed = hash_api_key(key)
    
    print(f"\nKey: {key}")
    print(f"Prefix: {prefix}")
    print(f"Hashed: {hashed[:70]}...")  # Show first 70 chars
    print(f"Full hash length: {len(hashed)}")
    
# Verify specific example for Rust implementation
specific_key = "testkey1.secretpartofthekey123"
specific_hash = hash_api_key(specific_key)
print(f"\n\nFor Rust verification:")
print(f"Key: {specific_key}")
print(f"Full hash: {specific_hash}")