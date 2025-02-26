import { testRequest } from '../utils/testRequest';
import { EmbedUser } from '../users/EmbedUser';
import { AuthStrategy } from '../types';
import { HeaderKeyAuth } from '../auth/strategies';

const { EMBED_BASE_URL } = process.env;

const url = (subpath: string) => EMBED_BASE_URL + '/' + subpath;

describe('Embed', () => {
  let authStrategy: AuthStrategy;
  let address: string;
  let apiKey: string;
  let scorerId: string;

  beforeAll(async () => {
    ({ apiKey, scorerId, address } = await EmbedUser.get());
    authStrategy = new HeaderKeyAuth({ key: apiKey, header: 'X-API-Key' });
  });

  it('POST /embed/auto-verify', async () => {
    const response = await testRequest({
      url: url('embed/auto-verify'),
      method: 'POST',
      authStrategy,
      payload: {
        address,
        scorerId,
        credentialIds: [],
      },
    });

    expect(response).toHaveStatus(200);

    expect(response.data).toMatchObject({
      address,
      score: expect.any(String),
      passing_score: expect.any(Boolean),
      threshold: expect.any(String),
      error: null,
      stamps: expect.any(Object),
    });
  });

  it('GET /embed/stamps/metadata', async () => {
    const response = await testRequest<{ valid?: boolean; code?: number }[]>({
      url: url(`embed/stamps/metadata`),
      method: 'GET',
      authStrategy,
      payload: {
        scorerId,
      },
    });

    expect(response).toHaveStatus(200);
    expect(response.data.length).toBeGreaterThan(0);
  });

  it('GET /health', async () => {
    const response = await testRequest({
      url: url('health'),
      method: 'GET',
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      message: 'Ok',
    });
  });
});
