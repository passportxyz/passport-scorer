import { testRequest } from '../utils/testRequest';
import { PassportUIUser } from '../users';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/ceramic-cache/' + subpath;

describe('Ceramic Cache Public', () => {
  let address: string;

  beforeAll(async () => {
    ({ address } = await PassportUIUser.get());
  });

  it('GET /weights', async () => {
    const response = await testRequest({
      url: url('weights'),
      method: 'GET',
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toEqual(expect.any(Object));
  });

  it('GET /stamp', async () => {
    const response = await testRequest<{ success: boolean; stamps: unknown[] }>({
      url: url(`stamp?address=${address}`),
      method: 'GET',
    });

    expect(response).toHaveStatus(200);
    expect(response.data.success).toBe(true);
    expect(Array.isArray(response.data.stamps)).toBe(true);
  });
});
