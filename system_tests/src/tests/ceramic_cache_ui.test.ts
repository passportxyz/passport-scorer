import { DidSignAuth } from '../auth/strategies';
import { AuthStrategy } from '../types';
import { createTestDIDSession } from '../utils/dids';
import { testRequest } from '../utils/testRequest';
import { generateStamps } from '../generate';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/ceramic-cache/' + subpath;

describe('Ceramic Cache UI', () => {
  let authStrategy: AuthStrategy;

  beforeAll(async () => {
    const { did } = await createTestDIDSession();
    authStrategy = new DidSignAuth({ did });
  });

  it('POST stamps/bulk', async () => {
    const response = await testRequest({
      url: url('stamps/bulk'),
      method: 'POST',
      authStrategy,
      payload: generateStamps(1),
    });

    expect(response).toHaveStatus(201);
  });

  it('PATCH stamps/bulk', async () => {
    const stamps = generateStamps(3);

    // Add a couple stamps
    const addResponse = await testRequest({
      url: url('stamps/bulk'),
      method: 'PATCH',
      authStrategy,
      payload: stamps.slice(0, 2),
    });

    expect(addResponse).toHaveStatus(200);

    // Add one, remove one
    const mixedResponse = await testRequest<{ success: boolean; stamps: unknown[] }>({
      url: url('stamps/bulk'),
      method: 'PATCH',
      authStrategy,
      payload: [
        stamps[2], // Add new stamp
        { provider: stamps[0].provider }, // Remove existing stamp
      ],
    });

    expect(mixedResponse).toHaveStatus(200);

    const data = mixedResponse.data;

    expect(data.success).toBe(true);
    expect(data.stamps.length).toBe(2);
  });

  it('DELETE stamps/bulk', async () => {
    const stamps = generateStamps(1);
    const stampsToDelete = stamps.map(({ provider }) => ({ provider }));

    // We need to create a stamp first
    const patchResponse = await testRequest({
      url: url('stamps/bulk'),
      method: 'PATCH',
      authStrategy,
      payload: stamps,
    });

    expect(patchResponse).toHaveStatus(200);

    const deleteResponse = await testRequest({
      url: url('stamps/bulk'),
      method: 'DELETE',
      authStrategy,
      payload: stampsToDelete,
    });

    expect(deleteResponse).toHaveStatus(200);
  });
});
