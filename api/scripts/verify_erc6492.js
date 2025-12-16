#!/usr/bin/env node
/**
 * ERC-6492 signature verification using viem
 * Called from Python backend for smart wallet signatures
 *
 * Usage: node verify_erc6492.js <address> <message> <signature> <chainId>
 * Returns: "true" or "false" to stdout
 */

const { createPublicClient, http, hashMessage } = require('viem');
const { mainnet, base, optimism, arbitrum } = require('viem/chains');

const chains = {
  1: mainnet,
  8453: base,
  10: optimism,
  42161: arbitrum,
};

async function verify() {
  const [,, address, message, signature, chainIdStr] = process.argv;

  if (!address || !message || !signature || !chainIdStr) {
    console.error('Usage: node verify_erc6492.js <address> <message> <signature> <chainId>');
    process.exit(1);
  }

  const chainId = parseInt(chainIdStr, 10);
  const chain = chains[chainId] || mainnet;

  const client = createPublicClient({
    chain,
    transport: http(),
  });

  try {
    const isValid = await client.verifyMessage({
      address,
      message,
      signature,
    });
    console.log(isValid ? 'true' : 'false');
  } catch (error) {
    console.error('Error:', error.message);
    console.log('false');
  }
}

verify();
