import { didSignAuth } from '../auth/strategies/didSignAuth';
import { Authenticate } from '../types';
import { createTestDID } from '../utils/dids';
import { testRequest } from '../utils/testRequest';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/ceramic-cache/' + subpath;

describe('Ceramic Cache UI', () => {
  let authenticate: Authenticate;

  beforeAll(async () => {
    const { did } = await createTestDID();
    authenticate = didSignAuth({ did });
  });

  it('should PATCH stamps', async () => {
    const response = await testRequest({
      url: url('stamps/bulk'),
      method: 'PATCH',
      authenticate,
      payload: [
        {
          provider: 'Lens',
          stamp: {
            address: '0x85ff01cff157199527528788ec4ea6336615c989',
            provider: 'Lens',
            issuer: 'did:ethr:0xd6f8d6ca86aa01e551a311d670a0d1bd8577e5fb',
            issuanceDate: '2024-08-01T10:15:26.579Z',
            expirationDate: '2024-10-30T10:15:26.579Z',
            proof: { proofValue: 'abc123' },
          },
        },
      ],
    });

    expect(response.status).toBe(200);
  });
});
