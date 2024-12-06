import { DIDSession } from 'did-session';
import { Wallet, providers } from 'ethers';
import { AccountId } from 'caip';
import { EthereumNodeAuth } from '@didtools/pkh-ethereum';
import { Eip1193Bridge } from './bridge';

const testPrivateKey = '0xc4aa93fe0b965ecaa4303fe3ef5554c428891b79d069f5b905397f286060007a';

// Helper function to create a new DID for testing
export const createTestDIDSession = async () => {
  // create ethers wallet
  const provider = new providers.AlchemyProvider('mainnet', process.env.ALCHEMY_API_KEY);
  const wallet = new Wallet(testPrivateKey);

  const address = wallet.address;

  const accountId = new AccountId({
    chainId: 'eip155:1',
    address,
  });

  const eip1193Provider = new Eip1193Bridge(wallet, provider);

  const authMethod = await EthereumNodeAuth.getAuthMethod(
    eip1193Provider,
    accountId,
    'system-test'
  );

  const session = await DIDSession.authorize(authMethod, {
    resources: ['ceramic://*'],
    domain: 'system-test',
  });

  return {
    session,
    address,
    did: session.did,
  };
};
