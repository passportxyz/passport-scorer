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

  it('PATCH stamps/bulk', async () => {
    const response = await testRequest({
      url: url('stamps/bulk'),
      method: 'PATCH',
      authenticate,
      payload: generateStamps(1),
    });

    expect(response.status).toBe(200);
  });

  it('DELETE stamps/bulk', async () => {
    const stamps = generateStamps(1);
    const stampsToDelete = stamps.map((stamp) => {
      return {
        provider: stamp.provider,
      };
    });

    // We need to create a stamp first
    const patchResponse = await testRequest({
      url: url('stamps/bulk'),
      method: 'PATCH',
      authenticate,
      payload: stamps,
    });

    expect(patchResponse.status).toBe(200);

    const deleteResponse = await testRequest({
      url: url('stamps/bulk'),
      method: 'DELETE',
      authenticate,
      payload: stampsToDelete,
    });

    // console.log("")
    expect(deleteResponse.status).toBe(200);
  });
});
