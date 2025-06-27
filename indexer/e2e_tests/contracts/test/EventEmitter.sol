// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract EventEmitter {
    // Staking events - must match IdentityStaking.sol signatures exactly
    event SelfStake(address indexed staker, uint88 amount, uint64 unlockTime);
    event CommunityStake(address indexed staker, address indexed stakee, uint88 amount, uint64 unlockTime);
    event SelfStakeWithdrawn(address indexed staker, uint88 amount);
    event CommunityStakeWithdrawn(address indexed staker, address indexed stakee, uint88 amount);
    event Slash(address indexed staker, address indexed stakee, uint88 amount, uint16 round);
    event Release(address indexed staker, address indexed stakee, uint88 amount);
    event Burn(address indexed staker, address indexed stakee, uint88 amount);
    
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
        emit SelfStake(staker, uint88(amount), uint64(unlockTime));
    }
    
    function emitCommunityStake(address staker, address stakee, uint256 amount, uint256 unlockTime) external {
        emit CommunityStake(staker, stakee, uint88(amount), uint64(unlockTime));
    }
    
    function emitSelfStakeWithdrawn(address staker, uint256 amount) external {
        emit SelfStakeWithdrawn(staker, uint88(amount));
    }
    
    function emitCommunityStakeWithdrawn(address staker, address stakee, uint256 amount) external {
        emit CommunityStakeWithdrawn(staker, stakee, uint88(amount));
    }
    
    function emitSlash(address staker, address stakee, uint256 amount, uint256 round) external {
        emit Slash(staker, stakee, uint88(amount), uint16(round));
    }
    
    function emitRelease(address staker, address stakee, uint256 amount) external {
        emit Release(staker, stakee, uint88(amount));
    }
    
    function emitBurn(address staker, address stakee, uint256 amount) external {
        emit Burn(staker, stakee, uint88(amount));
    }
    
    // Legacy support for tests
    function emitWithdraw(address staker, uint256 amount) external {
        // Assume self-stake withdrawal
        emit SelfStakeWithdrawn(staker, uint88(amount));
    }
    
    function emitSlash(address[] memory users, uint256[] memory amounts) external {
        // Emit individual slash events
        for (uint i = 0; i < users.length; i++) {
            emit Slash(users[i], users[i], uint88(amounts[i]), 0);
        }
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