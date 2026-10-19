/// Shared utility functions for API handlers

/// Validate Ethereum address format.
/// The zero address is rejected: nobody controls it, so a score for it is meaningless.
pub fn is_valid_eth_address(address: &str) -> bool {
    address.len() == 42 && address.starts_with("0x") &&
    address[2..].chars().all(|c| c.is_ascii_hexdigit()) &&
    !address[2..].chars().all(|c| c == '0')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_normal_address() {
        assert!(is_valid_eth_address("0x71ad3e3057ca74967239c66ca6d3a9c2a43a58fc"));
    }

    #[test]
    fn rejects_zero_address() {
        assert!(!is_valid_eth_address("0x0000000000000000000000000000000000000000"));
    }

    #[test]
    fn rejects_bad_format() {
        assert!(!is_valid_eth_address(":address"));
        assert!(!is_valid_eth_address("0x71ad3e3057ca74967239c66ca6d3a9c2a43a58f"));
    }
}