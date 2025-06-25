// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract EventEmitter {
    // Staking events
    event SelfStake(address indexed staker, uint256 amount, uint256 unlock_time);
    event CommunityStake(address indexed staker, address indexed stakee, uint256 amount, uint256 unlock_time);
    event Withdraw(address indexed staker, uint256 amount);
    event WithdrawFor(address indexed staker, address indexed stakee, uint256 amount);
    event WithdrawInBatch(address[] stakers, address[] stakees, uint256[] amounts);
    event Slash(address[] users, uint256[] amounts);
    event Release(address indexed user, uint256 amount);
    
    // Human Points events (EAS style)
    event Attested(
        address indexed recipient,
        address indexed attester,
        bytes32 uid,
        bytes32 indexed schemaId
    );
    
    // Human ID SBT events
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    
    // Schema IDs for different chains
    mapping(uint256 => bytes32) public passportSchemaIds;
    
    constructor() {
        // Initialize passport schema IDs for each chain
        passportSchemaIds[10] = 0xda0257756063c891659fed52fd36ef7557f7b45d66f59645fd3c3b263b747254; // Optimism
        passportSchemaIds[42161] = 0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912; // Arbitrum
        passportSchemaIds[8453] = 0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912; // Base
        passportSchemaIds[59144] = 0xa15ea01b11913fd412243156b40a8d5102ee9784172f82f9481e4c953fdd516d; // Linea
        passportSchemaIds[534352] = 0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912; // Scroll
        passportSchemaIds[324] = 0xb68405dffc0b727188de5a3af2ecbbc544ab01aef5353409c5006ffff342d143; // zkSync
        passportSchemaIds[360] = 0x1f3dce6501d8aad23563c0cf4f0c32264aed9311cb050056ebf72774f89ba912; // Shape
    }
    
    // Emit any event on demand
    function emitSelfStake(address staker, uint256 amount, uint256 unlockTime) external {
        emit SelfStake(staker, amount, unlockTime);
    }
    
    function emitCommunityStake(address staker, address stakee, uint256 amount, uint256 unlockTime) external {
        emit CommunityStake(staker, stakee, amount, unlockTime);
    }
    
    function emitWithdraw(address staker, uint256 amount) external {
        emit Withdraw(staker, amount);
    }
    
    function emitWithdrawFor(address staker, address stakee, uint256 amount) external {
        emit WithdrawFor(staker, stakee, amount);
    }
    
    function emitWithdrawInBatch(address[] memory stakers, address[] memory stakees, uint256[] memory amounts) external {
        emit WithdrawInBatch(stakers, stakees, amounts);
    }
    
    function emitSlash(address[] memory users, uint256[] memory amounts) external {
        emit Slash(users, amounts);
    }
    
    function emitRelease(address user, uint256 amount) external {
        emit Release(user, amount);
    }
    
    function emitPassportAttestation(address recipient, bytes32 uid, uint256 chainId) external {
        bytes32 schemaId = passportSchemaIds[chainId];
        // Use default if chain not configured
        if (schemaId == 0) {
            schemaId = passportSchemaIds[10]; // Default to Optimism schema
        }
        emit Attested(recipient, msg.sender, uid, schemaId);
    }
    
    function emitCustomAttestation(address recipient, bytes32 uid, bytes32 schemaId) external {
        emit Attested(recipient, msg.sender, uid, schemaId);
    }
    
    function emitHumanIdMint(address to, uint256 tokenId) external {
        emit Transfer(address(0), to, tokenId);
    }
    
    function emitHumanIdTransfer(address from, address to, uint256 tokenId) external {
        emit Transfer(from, to, tokenId);
    }
}