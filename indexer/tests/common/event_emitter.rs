use ethers::prelude::*;
use std::sync::Arc;

abigen!(
    EventEmitterContract,
    r#"[
        event SelfStake(address indexed staker, uint256 amount, uint256 unlock_time)
        event CommunityStake(address indexed staker, address indexed stakee, uint256 amount, uint256 unlock_time)
        event Withdraw(address indexed staker, uint256 amount)
        event WithdrawFor(address indexed staker, address indexed stakee, uint256 amount)
        event WithdrawInBatch(address[] stakers, address[] stakees, uint256[] amounts)
        event Slash(address[] users, uint256[] amounts)
        event Release(address indexed user, uint256 amount)
        event Attested(address indexed recipient, address indexed attester, bytes32 uid, bytes32 indexed schemaId)
        event Transfer(address indexed from, address indexed to, uint256 indexed tokenId)
        
        function emitSelfStake(address staker, uint256 amount, uint256 unlockTime)
        function emitCommunityStake(address staker, address stakee, uint256 amount, uint256 unlockTime)
        function emitWithdraw(address staker, uint256 amount)
        function emitWithdrawFor(address staker, address stakee, uint256 amount)
        function emitWithdrawInBatch(address[] stakers, address[] stakees, uint256[] amounts)
        function emitSlash(address[] users, uint256[] amounts)
        function emitRelease(address user, uint256 amount)
        function emitPassportAttestation(address recipient, bytes32 uid, uint256 chainId)
        function emitCustomAttestation(address recipient, bytes32 uid, bytes32 schemaId)
        function emitHumanIdMint(address to, uint256 tokenId)
        function emitHumanIdTransfer(address from, address to, uint256 tokenId)
    ]"#
);

pub struct EventEmitter {
    pub contract: EventEmitterContract<SignerMiddleware<Arc<Provider<Http>>, LocalWallet>>,
    pub address: Address,
}

impl EventEmitter {
    pub fn new(address: Address, provider: Arc<Provider<Http>>) -> Result<Self, Box<dyn std::error::Error>> {
        // Create a wallet from Anvil's default test account #0
        // This is a well-known test key - DO NOT USE ON REAL NETWORKS!
        // Address: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
        const ANVIL_TEST_PRIVATE_KEY: &str = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";
        
        let wallet = ANVIL_TEST_PRIVATE_KEY
            .parse::<LocalWallet>()?
            .with_chain_id(10u64); // Hardcode chain ID for testing
        
        let client = SignerMiddleware::new(provider, wallet);
        let client = Arc::new(client);
        
        let contract = EventEmitterContract::new(address, client);
        
        Ok(Self { contract, address })
    }
    
    pub async fn emit_self_stake(
        &self,
        staker: Address,
        amount: U256,
        unlock_time: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_self_stake(staker, amount, unlock_time)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_community_stake(
        &self,
        staker: Address,
        stakee: Address,
        amount: U256,
        unlock_time: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_community_stake(staker, stakee, amount, unlock_time)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_withdraw(
        &self,
        staker: Address,
        amount: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_withdraw(staker, amount)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_withdraw_for(
        &self,
        staker: Address,
        stakee: Address,
        amount: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_withdraw_for(staker, stakee, amount)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_withdraw_in_batch(
        &self,
        stakers: Vec<Address>,
        stakees: Vec<Address>,
        amounts: Vec<U256>,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_withdraw_in_batch(stakers, stakees, amounts)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_slash(
        &self,
        users: Vec<Address>,
        amounts: Vec<U256>,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_slash(users, amounts)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_release(
        &self,
        user: Address,
        amount: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_release(user, amount)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_passport_attestation(
        &self,
        recipient: Address,
        uid: H256,
        chain_id: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_passport_attestation(recipient, uid.into(), chain_id)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_custom_attestation(
        &self,
        recipient: Address,
        uid: H256,
        schema_id: H256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_custom_attestation(recipient, uid.into(), schema_id.into())
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_human_id_mint(
        &self,
        to: Address,
        token_id: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_human_id_mint(to, token_id)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
    
    pub async fn emit_human_id_transfer(
        &self,
        from: Address,
        to: Address,
        token_id: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        let tx = self.contract
            .emit_human_id_transfer(from, to, token_id)
            .send()
            .await?
            .await?
            .ok_or("No receipt")?;
        Ok(tx)
    }
}