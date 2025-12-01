// API handlers - thin HTTP orchestration layer
// Handlers only deal with HTTP concerns:
// 1. Extract parameters from request
// 2. Perform authentication/authorization
// 3. Call domain logic
// 4. Transform domain result to HTTP response

pub mod ceramic_cache;
pub mod embed;
pub mod external;
pub mod internal;

// Re-export commonly used handlers
pub use ceramic_cache::{
    ceramic_cache_add_stamps, ceramic_cache_delete_stamps,
    ceramic_cache_get_score, ceramic_cache_get_stamp,
    ceramic_cache_get_weights, ceramic_cache_patch_stamps,
};
pub use embed::{add_stamps_handler, get_embed_score_handler, validate_api_key_handler};
pub use external::score_address_handler as external_score_handler;
pub use internal::{
    internal_allow_list_handler, internal_cgrants_statistics_handler,
    internal_check_bans_handler, internal_check_revocations_handler,
    internal_credential_definition_handler, internal_legacy_stake_handler,
    internal_score_handler, internal_stake_gtc_handler,
    internal_weights_handler,
};