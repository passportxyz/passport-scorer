use ethers::providers::{Provider, Ws};
use std::env;

pub fn get_env(var: &str) -> String {
    env::var(var).unwrap_or_else(|_| panic!("Required environment variable \"{}\" not set", var))
}

pub async fn create_rpc_connection(rpc_url: &String) -> Provider<Ws> {
    let mut num_retries = 0;
    let delay_base: u64 = 2;

    loop {
        match connect_with_reconnects(rpc_url).await {
            Some(p) => return p,
            None => {
                eprintln!(
                    "Warning - Failed to connect to RPC at {}, retry attempt #{}",
                    rpc_url, num_retries
                );
                tokio::time::sleep(tokio::time::Duration::from_secs(
                    delay_base.pow(num_retries),
                ))
                .await;
                if num_retries > 0 && num_retries % 4 == 0 {
                    eprintln!("Error - Failed repeatedly to connect to RPC at {}", rpc_url);
                }
                num_retries += 1;
            }
        }
    }
}

async fn connect_with_reconnects(rpc_url: &String) -> Option<Provider<Ws>> {
    match Provider::<Ws>::connect_with_reconnects(rpc_url, 0).await {
        Ok(p) => Some(p),
        Err(e) => {
            eprintln!("Warning - Stream reconnect attempt failed: {e}");
            None
        }
    }
}

#[derive(Copy, Clone)]
pub enum StakeAmountOperation {
    Add,
    Subtract,
}

pub enum StakeEventType {
    SelfStake,
    CommunityStake,
    SelfStakeWithdraw,
    CommunityStakeWithdraw,
    Slash,
    Release,
}

pub fn get_code_for_stake_event_type(event_type: &StakeEventType) -> &'static str {
    match event_type {
        StakeEventType::SelfStake => "SST",
        StakeEventType::CommunityStake => "CST",
        StakeEventType::SelfStakeWithdraw => "SSW",
        StakeEventType::CommunityStakeWithdraw => "CSW",
        StakeEventType::Slash => "SLA",
        StakeEventType::Release => "REL",
    }
}

impl StakeAmountOperation {
    #[cfg(test)]
    pub fn from_event_type(event_type: &StakeEventType) -> Self {
        match event_type {
            StakeEventType::SelfStake | StakeEventType::CommunityStake | StakeEventType::Release => {
                StakeAmountOperation::Add
            }
            StakeEventType::SelfStakeWithdraw
            | StakeEventType::CommunityStakeWithdraw
            | StakeEventType::Slash => StakeAmountOperation::Subtract,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stake_amount_operation_from_event_type() {
        // Test that Add operations are correctly identified
        assert!(matches!(
            StakeAmountOperation::from_event_type(&StakeEventType::SelfStake),
            StakeAmountOperation::Add
        ));
        assert!(matches!(
            StakeAmountOperation::from_event_type(&StakeEventType::CommunityStake),
            StakeAmountOperation::Add
        ));
        assert!(matches!(
            StakeAmountOperation::from_event_type(&StakeEventType::Release),
            StakeAmountOperation::Add
        ));

        // Test that Subtract operations are correctly identified
        assert!(matches!(
            StakeAmountOperation::from_event_type(&StakeEventType::SelfStakeWithdraw),
            StakeAmountOperation::Subtract
        ));
        assert!(matches!(
            StakeAmountOperation::from_event_type(&StakeEventType::CommunityStakeWithdraw),
            StakeAmountOperation::Subtract
        ));
        assert!(matches!(
            StakeAmountOperation::from_event_type(&StakeEventType::Slash),
            StakeAmountOperation::Subtract
        ));
    }

    #[test]
    fn test_stake_event_type_codes() {
        // Verify all event types have unique codes
        let codes = vec![
            get_code_for_stake_event_type(&StakeEventType::SelfStake),
            get_code_for_stake_event_type(&StakeEventType::CommunityStake),
            get_code_for_stake_event_type(&StakeEventType::SelfStakeWithdraw),
            get_code_for_stake_event_type(&StakeEventType::CommunityStakeWithdraw),
            get_code_for_stake_event_type(&StakeEventType::Slash),
            get_code_for_stake_event_type(&StakeEventType::Release),
        ];

        // Check all codes are unique
        let unique_codes: std::collections::HashSet<_> = codes.iter().collect();
        assert_eq!(codes.len(), unique_codes.len(), "Event type codes must be unique");

        // Verify specific mappings
        assert_eq!(get_code_for_stake_event_type(&StakeEventType::SelfStake), "SST");
        assert_eq!(get_code_for_stake_event_type(&StakeEventType::CommunityStake), "CST");
        assert_eq!(get_code_for_stake_event_type(&StakeEventType::SelfStakeWithdraw), "SSW");
        assert_eq!(get_code_for_stake_event_type(&StakeEventType::CommunityStakeWithdraw), "CSW");
        assert_eq!(get_code_for_stake_event_type(&StakeEventType::Slash), "SLA");
        assert_eq!(get_code_for_stake_event_type(&StakeEventType::Release), "REL");
    }
}
