import { randomBytes } from 'crypto';
import { DID } from 'dids';
import { Ed25519Provider } from 'key-did-provider-ed25519';
import KeyResolver from 'key-did-resolver';

// Helper function to create a new DID for testing
export const createTestDID = async () => {
  const seedBytes = randomBytes(32);
  const provider = new Ed25519Provider(seedBytes);
  const did = new DID({
    provider,
    resolver: KeyResolver.getResolver(),
  });
  await did.authenticate();

  const seed = Buffer.from(seedBytes).toString('hex');

  return {
    did,
    seed,
  };
};
