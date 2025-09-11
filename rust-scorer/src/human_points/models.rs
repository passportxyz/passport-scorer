use std::collections::HashMap;
use once_cell::sync::Lazy;

/// Human Points action types - matches Django HumanPoints.Action choices
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum HumanPointsAction {
    ScoringBonus,       // SCB
    HumanKeys,          // HKY
    IdentityStakingBronze,      // ISB
    IdentityStakingSilver,      // ISS
    IdentityStakingGold,        // ISG
    CommunityStakingBeginner,   // CSB
    CommunityStakingExperienced, // CSE
    CommunityStakingTrusted,    // CST
    PassportMint,       // PMT
    HumanIdMint,        // HIM
    HumanTechGovId,     // HGO
    HumanTechPhone,     // HPH
    HumanTechCleanHands,// HCH
    HumanTechBiometric, // HBI
    MetamaskOg,         // MTA
}

impl HumanPointsAction {
    /// Get the database string representation (3-letter code)
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::ScoringBonus => "SCB",
            Self::HumanKeys => "HKY",
            Self::IdentityStakingBronze => "ISB",
            Self::IdentityStakingSilver => "ISS",
            Self::IdentityStakingGold => "ISG",
            Self::CommunityStakingBeginner => "CSB",
            Self::CommunityStakingExperienced => "CSE",
            Self::CommunityStakingTrusted => "CST",
            Self::PassportMint => "PMT",
            Self::HumanIdMint => "HIM",
            Self::HumanTechGovId => "HGO",
            Self::HumanTechPhone => "HPH",
            Self::HumanTechCleanHands => "HCH",
            Self::HumanTechBiometric => "HBI",
            Self::MetamaskOg => "MTA",
        }
    }
}

/// Map stamp providers to Human Points actions
/// Matches Python's STAMP_PROVIDER_TO_ACTION
pub static STAMP_PROVIDER_TO_ACTION: Lazy<HashMap<&'static str, HumanPointsAction>> = Lazy::new(|| {
    let mut m = HashMap::new();
    m.insert("SelfStakingBronze", HumanPointsAction::IdentityStakingBronze);
    m.insert("SelfStakingSilver", HumanPointsAction::IdentityStakingSilver);
    m.insert("SelfStakingGold", HumanPointsAction::IdentityStakingGold);
    m.insert("BeginnerCommunityStaker", HumanPointsAction::CommunityStakingBeginner);
    m.insert("ExperiencedCommunityStaker", HumanPointsAction::CommunityStakingExperienced);
    m.insert("TrustedCitizen", HumanPointsAction::CommunityStakingTrusted);
    m.insert("HolonymGovIdProvider", HumanPointsAction::HumanTechGovId);
    m.insert("HolonymPhone", HumanPointsAction::HumanTechPhone);
    m.insert("CleanHands", HumanPointsAction::HumanTechCleanHands);
    m.insert("Biometrics", HumanPointsAction::HumanTechBiometric);
    m
});