import { DIDSession } from 'did-session';
import { Wallet, providers } from 'ethers';
import { AccountId } from 'caip';
import { EthereumNodeAuth } from '@didtools/pkh-ethereum';
import { Eip1193Bridge } from './bridge';

// Helper function to create a new DID for testing
export const createTestDIDSession = async ({
  wallet,
  provider,
}: {
  wallet: Wallet;
  provider: providers.Provider;
}) => {
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
    did: session.did,
  };
};
