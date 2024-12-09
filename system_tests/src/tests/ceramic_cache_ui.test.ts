import { DidSignAuth } from '../auth/strategies';
import { AuthStrategy } from '../types';
import { testRequest } from '../utils/testRequest';
import { generateStamps } from '../generate';
import { PassportUIUser } from '../users';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/ceramic-cache/' + subpath;

describe('Ceramic Cache DID', () => {
  let authStrategy: AuthStrategy;
  let address: string;
  let scorerId: string;

  beforeAll(async () => {
    let did;
    ({ did, address, scorerId } = await PassportUIUser.get());
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

  // it('GET /score/{address}', async () => {
  //   const response = await testRequest({
  //     url: url(`score/${address}`),
  //     method: 'GET',
  //     authStrategy,
  //   });

  //   expect(response).toHaveStatus(200);
  // });

  // it('POST /score/{address}', async () => {
  //   const response = await testRequest({
  //     url: url(`score/${address}`),
  //     method: 'POST',
  //     authStrategy,
  //     payload: {
  //       alternate_scorer_id: 1,
  //     },
  //   });

  //   expect(response).toHaveStatus(200);
  // });

  // it('GET /score/{scorer_id}/{address}', async () => {
  //   const response = await testRequest({
  //     url: url(`score/${scorerId}/${address}`),
  //     method: 'GET',
  //     authStrategy: secretKeyAuthStrategy,
  //   });

  //   expect(response).toHaveStatus(200);
  // });

  // it('GET /stake/gtc', async () => {
  //   const response = await testRequest({
  //     url: url('stake/gtc'),
  //     method: 'GET',
  //     authStrategy,
  //   });

  //   expect(response).toHaveStatus(200);
  //   expect(response.data).toHaveProperty('items');
  // });

  // it('GET /tos/accepted/{tos_type}/{address}', async () => {
  //   const response = await testRequest({
  //     url: url(`tos/accepted/${testTosType}/${address}`),
  //     method: 'GET',
  //     authStrategy,
  //   });

  //   expect(response).toHaveStatus(200);
  // });

  // it('GET /tos/message-to-sign/{tos_type}/{address}', async () => {
  //   const response = await testRequest({
  //     url: url(`tos/message-to-sign/${testTosType}/${address}`),
  //     method: 'GET',
  //     authStrategy,
  //   });

  //   expect(response).toHaveStatus(200);
  // });

  // it('POST /tos/signed-message/{tos_type}/{address}', async () => {
  //   const response = await testRequest({
  //     url: url(`tos/signed-message/${testTosType}/${address}`),
  //     method: 'POST',
  //     authStrategy,
  //     payload: {
  //       signedMessage: 'test-signed-message',
  //     },
  //   });

  //   expect(response).toHaveStatus(200);
  // });
});

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
