import { DidSignAuth } from '../auth/strategies';
import { AuthStrategy } from '../types';
import { testRequest } from '../utils/testRequest';
import { generateStamps } from '../generate';
import { PassportUIUser } from '../users';
import { Signer } from 'ethers';

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + '/ceramic-cache/' + subpath;

describe('Ceramic Cache DID', () => {
  let authStrategy: AuthStrategy;
  let address: string;
  let signer: Signer;

  beforeAll(async () => {
    let did;
    ({ did, address, signer } = await PassportUIUser.get());
    authStrategy = new DidSignAuth({ did });
  });

  it('POST /stamps/bulk', async () => {
    const response = await testRequest({
      url: url('stamps/bulk'),
      method: 'POST',
      authStrategy,
      payload: generateStamps(1),
    });

    expect(response).toHaveStatus(201);
  });

  it('PATCH /stamps/bulk', async () => {
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

  it('DELETE /stamps/bulk', async () => {
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

  it('GET /score/{address}', async () => {
    const response = await testRequest({
      url: url(`score/${address}`),
      method: 'GET',
      authStrategy,
    });

    expect(response).toHaveStatus(200);
  });

  it('POST /score/{address}', async () => {
    const response = await testRequest({
      url: url(`score/${address}`),
      method: 'POST',
      authStrategy,
      payload: {
        alternate_scorer_id: process.env.TEST_API_SCORER_ID,
      },
    });

    expect(response).toHaveStatus(200);
  });

  it('GET /stake/gtc', async () => {
    const response = await testRequest({
      url: url('stake/gtc'),
      method: 'GET',
      authStrategy,
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toHaveProperty('items');
  });

  it('GET /tos/accepted/{tos_type}/{address}', async () => {
    const response = await testRequest({
      url: url(`tos/accepted/IST/${address}`),
      method: 'GET',
      authStrategy,
    });

    expect(response).toHaveStatus(200);
  });

  it('GET /tos/message-to-sign/{tos_type}/{address}', async () => {
    const response = await testRequest({
      url: url(`tos/message-to-sign/IST/${address}`),
      method: 'GET',
      authStrategy,
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      text: expect.any(String),
      nonce: expect.any(String),
    });
  });

  it('POST /tos/signed-message/{tos_type}/{address}', async () => {
    const messageResponse = await testRequest<{ text: string; nonce: string }>({
      url: url(`tos/message-to-sign/IST/${address}`),
      method: 'GET',
      authStrategy,
    });

    expect(messageResponse).toHaveStatus(200);
    expect(messageResponse.data).toMatchObject({
      text: expect.any(String),
      nonce: expect.any(String),
    });

    const { text, nonce } = messageResponse.data;

    const signature = await signer.signMessage(text);

    const verificationResponse = await testRequest<{}>({
      url: url(`tos/signed-message/IST/${address}`),
      method: 'POST',
      authStrategy,
      payload: {
        nonce,
        signature,
        tos_type: 'IST',
      },
    });

    expect(verificationResponse).toHaveStatus(200);
  });
});
