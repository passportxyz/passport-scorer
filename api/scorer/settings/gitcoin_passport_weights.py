"""Configuration for the gitcoin scorer"""

# Weight values for each stamp based on its perceived significance in assessing the unique humanity of the Passport holder
GITCOIN_PASSPORT_WEIGHTS = {
    "Brightid": "0.709878",
    "CivicCaptchaPass": "0.510878",
    "CivicLivenessPass": "2.270878",
    "CivicUniquenessPass": "3.289378",
    "CoinbaseDualVerification": "1.370878",
    "CommunityStakingBronze": "0.020878",
    "CommunityStakingGold": "0.020878",
    "CommunityStakingSilver": "0.020878",
    "Discord": "0.709878",
    "Ens": "2.220878",
    "GitcoinContributorStatistics#numGrantsContributeToGte#1": "2.930878",
    "GitcoinContributorStatistics#numGrantsContributeToGte#10": "3.660878",
    "GitcoinContributorStatistics#numGrantsContributeToGte#25": "2.840878",
    "GitcoinContributorStatistics#numGrantsContributeToGte#100": "1.880878",
    "GitcoinContributorStatistics#totalContributionAmountGte#10": "2.940878",
    "GitcoinContributorStatistics#totalContributionAmountGte#100": "2.730878",
    "GitcoinContributorStatistics#totalContributionAmountGte#1000": "2.540878",
    "githubAccountCreationGte#90": "1.020878",
    "githubAccountCreationGte#365": "1.430878",
    "githubAccountCreationGte#180": "1.230878",
    "githubContributionActivityGte#120": "1.230878",
    "githubContributionActivityGte#30": "1.230878",
    "githubContributionActivityGte#60": "1.230878",
    "GnosisSafe": "2.670878",
    "Google": "1.030878",
    "GuildAdmin": "0.709878",
    "GuildMember": "0.709878",
    "GuildPassportMember": "0.709878",
    "HolonymGovIdProvider": "5.039378",
    "IdenaAge#10": "1.500878",
    "IdenaAge#5": "1.500878",
    "IdenaStake#100k": "1.430878",
    "IdenaStake#10k": "1.180878",
    "IdenaStake#1k": "0.920878",
    "IdenaState#Human": "1.630878",
    "IdenaState#Newbie": "0.530878",
    "IdenaState#Verified": "1.370878",
    "Lens": "2.470878",
    "Linkedin": "1.040878",
    "NFT": "0.710878",
    "PHIActivityGold": "1.180878",
    "PHIActivitySilver": "1.690878",
    "Poh": "1.230878",
    "SelfStakingBronze": "1.230878",
    "SelfStakingGold": "1.230878",
    "SelfStakingSilver": "1.230878",
    "BeginnerCommunityStaker": "1.290878",
    "ExperiencedCommunityStaker": "1.290878",
    "TrustedCitizen": "1.290878",
    "SnapshotProposalsProvider": "2.840878",
    "SnapshotVotesProvider": "1.430878",
    "twitterAccountAgeGte#180": "1.020878",
    "twitterAccountAgeGte#365": "1.230878",
    "twitterAccountAgeGte#730": "1.430878",
    "ZkSync": "0.420878",
    "ZkSyncEra": "0.420878",
    "CyberProfilePremium": "1.230878",
    "CyberProfilePaid": "1.230878",
    "CyberProfileOrgMember": "1.230878",
    "TrustaLabs": "2.020878",
    "ETHAdvocate": "3.54",
    "ETHPioneer": "3.54",
    "ETHMaxi": "3.54",
}


# The Boolean scorer deems Passport holders unique humans if they meet or exceed the below thresholdold
GITCOIN_PASSPORT_THRESHOLD = "20"


def increment_scores(increment_value):
    for key, value in GITCOIN_PASSPORT_WEIGHTS.copy().items():
        updated_value = float(value) + increment_value
        print(f'"{key}": "{updated_value:.6f}",')
