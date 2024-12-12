import { HeaderKeyAuth } from '../auth/strategies';
import { AuthStrategy } from '../types';
import { testRequest } from '../utils/testRequest';
import { generatePassportAddress } from '../generate';
import { RegistryAPIUser } from '../users';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/v2/' + subpath;

describe('V2 API', () => {
  let authStrategy: AuthStrategy;
  let address: string;
  let scorerId: string;

  beforeAll(async () => {
    const registryAPIUser = await RegistryAPIUser.get();
    scorerId = registryAPIUser.scorerId;

    authStrategy = new HeaderKeyAuth({ key: registryAPIUser.apiKey, header: 'X-API-Key' });
    address = generatePassportAddress();
  });

  describe('/stamps', () => {
    it('GET /stamps/{scorer_id}/score/{address}', async () => {
      const response = await testRequest({
        url: url(`stamps/${scorerId}/score/${address}`),
        method: 'GET',
        authStrategy,
      });

      expect(response).toHaveStatus(200);
      expect(response.data).toMatchObject({
        address,
        score: expect.any(String),
      });
    });

    it('GET /stamps/{scorer_id}/score/{address}/history', async () => {
      const response = await testRequest({
        url: url(`stamps/${scorerId}/score/${address}/history`),
        method: 'GET',
        authStrategy,
        payload: {
          created_at: new Date().toISOString(),
        },
      });

      expect(response).toHaveStatus(200);
      expect(response.data).toMatchObject({
        address,
        score: expect.any(String),
      });
    });

    it('GET /stamps/metadata', async () => {
      const response = await testRequest<unknown[]>({
        url: url('stamps/metadata'),
        method: 'GET',
        authStrategy,
      });

      expect(response).toHaveStatus(200);
      expect(Array.isArray(response.data)).toBe(true);
      expect(response.data[0]).toMatchObject({
        id: expect.any(String),
        icon: expect.any(String),
        name: expect.any(String),
        description: expect.any(String),
        connectMessage: expect.any(String),
        groups: expect.arrayContaining([
          expect.objectContaining({
            name: expect.any(String),
            stamps: expect.arrayContaining([
              expect.objectContaining({
                name: expect.any(String),
                description: expect.any(String),
                hash: expect.any(String),
              }),
            ]),
          }),
        ]),
      });
    });

    it('GET /stamps/{address}?include_metadata=true', async () => {
      const response = await testRequest({
        url: url(`stamps/${address}?include_metadata=true`),
        method: 'GET',
        authStrategy,
      });

      expect(response).toHaveStatus(200);
      expect(response.data).toMatchObject({
        items: expect.arrayContaining([
          expect.objectContaining({
            version: expect.any(String),
            credential: expect.any(Object),
            metadata: expect.objectContaining({
              group: expect.any(String),
              platform: expect.objectContaining({
                id: expect.any(String),
                icon: expect.any(String),
                name: expect.any(String),
                description: expect.any(String),
                connectMessage: expect.any(String),
              }),
            }),
          }),
        ]),
      });
    });
  });

  describe('/models', () => {
    it('GET /models/score/{address}?model=aggregate', async () => {
      const model = 'aggregate';
      const response = await testRequest({
        url: url(`models/score/${address}?model=${model}`),
        method: 'GET',
        authStrategy,
      });

      expect(response).toHaveStatus(200);
      expect(response.data).toMatchObject({
        address,
        details: {
          models: {
            [model]: {
              score: expect.any(Number),
            },
          },
        },
      });
    });
  });
});
