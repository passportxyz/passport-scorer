import { HeaderKeyAuth } from '../auth/strategies';
import { AuthStrategy } from '../types';
import { testRequest } from '../utils/testRequest';
import { generatePassportAddress } from '../generate';
import { RegistryAPIUser } from '../users';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/registry/' + subpath;

describe('Registry API', () => {
  let authStrategy: AuthStrategy;
  let address: string;
  let scorerId: string;

  beforeAll(async () => {
    const registryAPIUser = await RegistryAPIUser.get();
    scorerId = registryAPIUser.scorerId;

    authStrategy = new HeaderKeyAuth({ key: registryAPIUser.apiKey, header: 'X-API-Key' });
    address = generatePassportAddress();
  });

  describe('Submit Passport and Get Score', () => {
    it('should submit passport and get processing status', async () => {
      const submitResponse = await testRequest({
        url: url('submit-passport'),
        method: 'POST',
        authStrategy,
        payload: {
          address,
          scorer_id: scorerId,
        },
      });

      expect(submitResponse).toHaveStatus(200);
      expect(submitResponse.data).toMatchObject({
        address: expect.any(String),
        status: 'DONE',
      });
    });

    it('should get score for specific address', async () => {
      const getScoreResponse = await testRequest({
        url: url(`score/${scorerId}/${address}`),
        method: 'GET',
        authStrategy,
      });

      expect(getScoreResponse).toHaveStatus(200);
      expect(getScoreResponse.data).toMatchObject({
        address: expect.any(String),
        status: 'DONE',
      });
    });

    it('should get paginated list of scores', async () => {
      const getScoresResponse = await testRequest<{ items?: unknown[] }>({
        url: url(`score/${scorerId}`),
        method: 'GET',
        authStrategy,
        payload: {
          limit: 10,
          offset: 0,
        },
      });

      expect(getScoresResponse).toHaveStatus(200);
      console.log(getScoresResponse.data);
      expect(Array.isArray(getScoresResponse.data.items)).toBe(true);

      if (getScoresResponse.data.items!.length) {
        expect(getScoresResponse.data.items![0]).toMatchObject({
          address: expect.any(String),
          status: 'DONE',
        });
      }
    });
  });

  // Test for /signing-message endpoint
  it('should get signing message', async () => {
    const response = await testRequest({
      url: url('signing-message'),
      method: 'GET',
      authStrategy,
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      message: expect.any(String),
      nonce: expect.any(String),
    });
  });

  // Test for /stamps/{address} endpoint
  it('should get passport stamps for address', async () => {
    const response = await testRequest({
      url: url(`stamps/${address}`),
      method: 'GET',
      authStrategy,
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      next: expect.any(String) || null,
      prev: expect.any(String) || null,
      items: expect.arrayContaining([
        expect.objectContaining({
          version: expect.any(String),
          credential: expect.any(Object),
        }),
      ]),
    });
  });

  // Test for /stamps/{address} with metadata
  it('should get passport stamps with metadata', async () => {
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

  // Test for /stamp-metadata endpoint
  it('should get all available stamp metadata', async () => {
    const response = await testRequest({
      url: url('stamp-metadata'),
      method: 'GET',
      authStrategy,
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toBeArray();
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

  // Test for /gtc-stake/{address}/{round_id} endpoint
  it('should get GTC stake events', async () => {
    const roundId = 1;
    const response = await testRequest({
      url: url(`gtc-stake/${address}/${roundId}`),
      method: 'GET',
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      results: expect.arrayContaining([
        expect.objectContaining({
          id: expect.any(Number),
          event_type: expect.any(String),
          round_id: expect.any(Number),
          staker: expect.any(String),
          amount: expect.any(String),
          staked: expect.any(Boolean),
          block_number: expect.any(Number),
          tx_hash: expect.any(String),
        }),
      ]),
    });
  });
});
