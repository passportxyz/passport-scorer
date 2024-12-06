import { didSignAuth } from '../auth/didSignAuth';
import { Authenticate } from '../types';
import { createTestDIDSession } from '../utils/dids';
import { testRequest } from '../utils/testRequest';
import { generateStamps } from '../generate';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/ceramic-cache/' + subpath;

describe('Ceramic Cache UI', () => {
  let authenticate: Authenticate;

  beforeAll(async () => {
    const { did } = await createTestDIDSession();
    authenticate = didSignAuth({ did });
  });

  it('should PATCH stamps', async () => {
    const response = await testRequest({
      url: url('stamps/bulk'),
      method: 'PATCH',
      authenticate,
      payload: generateStamps(1),
    });

    expect(response.status).toBe(200);
  });
});
