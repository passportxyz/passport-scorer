# DIDKit Rust EIP-712 Signing Requirements

## TypedData Structure Requirement

When signing credentials with EthereumEip712Signature2021 using DIDKit's Rust SSI library, the eip712_domain field in LinkedDataProofOptions must be a properly structured TypedData object from `ssi::ldp::eip712`, not a raw JSON value.

The library expects the domain, types, and primaryType to be in the correct format that matches the TypedData struct definition.

## Credential @context Structure

When creating Passport credentials with EthereumEip712Signature2021 signatures, the nested JSON-LD context object must be placed in `credentialSubject.@context`, NOT in the top-level credential @context array.

### Top-level @context
Should only contain URI strings:
```json
{
  "@context": [
    "https://www.w3.org/2018/credentials/v1",
    "https://w3id.org/vc/status-list/2021/v1"
  ]
}
```

### Nested Context in credentialSubject
The nested definitions go here:
```json
{
  "credentialSubject": {
    "@context": {
      "provider": "https://schema.org/Text",
      "nullifiers": {
        "@type": "https://schema.org/Text",
        "@container": "@list"
      }
    }
  }
}
```

This structure allows DIDKit's EIP-712 TypedData generator to properly parse the credential without "Expected string" errors.

See: `rust-scorer/comparison-tests/src/gen_credentials.rs`
