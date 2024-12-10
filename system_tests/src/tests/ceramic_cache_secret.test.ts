import { HeaderKeyAuth } from '../auth/strategies';
import { AuthStrategy } from '../types';
import { testRequest } from '../utils/testRequest';
import { InternalAPIUser, PassportUIUser } from '../users';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/ceramic-cache/' + subpath;

describe('Ceramic Cache Secret', () => {
  let authStrategy: AuthStrategy;

  let address: string;
  let scorerId: string;

  beforeAll(async () => {
    const internalApiUser = await InternalAPIUser.get();
    const uiUser = await PassportUIUser.get();

    authStrategy = new HeaderKeyAuth({ key: internalApiUser.apiSecret });
    scorerId = internalApiUser.scorerId;
    address = uiUser.address;
  });

  it('GET /score/{scorer_id}/{address}', async () => {
    const response = await testRequest({
      url: url(`score/${scorerId}/${address}`),
      method: 'GET',
      authStrategy,
    });

    expect(response).toHaveStatus(200);
  });
});
