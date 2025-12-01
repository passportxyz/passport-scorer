// Database queries organized by domain
// Each module contains focused queries for a specific domain area

pub mod scoring;
pub mod stamps;
pub mod bans;
pub mod stakes;
pub mod cgrants;
pub mod weights;
pub mod utils;
pub mod dedup;

// Re-export commonly used query functions
pub use scoring::{get_passport, upsert_passport_record, get_score, upsert_score_record, load_community, upsert_score};
pub use stamps::{get_ceramic_cache_entries, get_latest_stamps_by_provider, delete_stamps, bulk_insert_stamps};
pub use weights::{get_scorer_weights, get_default_scorer_weights, load_scorer_config};
pub use utils::{check_community_exists, get_allow_list_membership};
pub use dedup::{load_hash_scorer_links, bulk_upsert_hash_links, verify_hash_links, insert_dedup_events, insert_score_update_event};