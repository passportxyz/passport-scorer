import { HeaderKeyAuth } from '../auth/strategies';
import { AuthStrategy } from '../types';
import { testRequest } from '../utils/testRequest';
import { generatePassportAddress } from '../generate';
import { RegistryAPIUser } from '../users';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/passport/' + subpath;

describe('Passport API', () => {
  let authStrategy: AuthStrategy;
  let address: string;

  beforeAll(async () => {
    const registryAPIUser = await RegistryAPIUser.get();

    authStrategy = new HeaderKeyAuth({ key: registryAPIUser.apiKey, header: 'X-API-Key' });
    address = generatePassportAddress();
  });

  it('GET /passport/analysis/{address}', async () => {
    const model = 'aggregate';
    const response = await testRequest({
      url: url(`analysis/${address}`),
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
