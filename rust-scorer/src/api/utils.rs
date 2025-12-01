/// Shared utility functions for API handlers

/// Validate Ethereum address format
pub fn is_valid_eth_address(address: &str) -> bool {
    address.len() == 42 && address.starts_with("0x") &&
    address[2..].chars().all(|c| c.is_ascii_hexdigit())
}