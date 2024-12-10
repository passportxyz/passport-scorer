import { testRequest } from '../utils/testRequest';
import { PassportUIUser } from '../users';
import { DID } from 'dids';
import { createSignedPayload } from '../utils/dids';
import { generateEVMProviders } from '../generate';
import { Wallet } from 'ethers';

const { IAM_BASE_URL } = process.env;

const version = '0.0.0';
const url = (subpath: string) => IAM_BASE_URL + '/api/v' + version + '/' + subpath;

describe('IAM (Simple)', () => {
  let address: string;
  let did: DID;

  beforeAll(async () => {
    ({ did, address } = await PassportUIUser.get());
  });

  it('POST /verify (also tests POST /challenge)', async () => {
    const type = 'Simple';

    const challengeResponse = await testRequest<{
      credential?: { credentialSubject?: { challenge?: unknown } };
    }>({
      url: url(`challenge`),
      method: 'POST',
      payload: {
        payload: {
          address,
          type,
        },
      },
    });

    expect(challengeResponse).toHaveStatus(200);

    const challenge = challengeResponse.data.credential;
    const challengeMessage = challenge?.credentialSubject?.challenge;

    expect(challengeMessage).toBeDefined();

    const signedChallenge = await createSignedPayload(did, challengeMessage);

    const verifyResponse = await testRequest({
      url: url(`verify`),
      method: 'POST',
      payload: {
        challenge,
        signedChallenge,
        payload: {
          address,
          type,
          signatureType: 'EIP712',
          version,
          proofs: {
            valid: 'true',
            username: 'test',
            signature: 'pass',
          },
        },
      },
    });

    expect(verifyResponse).toHaveStatus(200);
    expect(verifyResponse.data).toMatchObject({
      record: {
        type,
      },
      credential: {
        credentialSubject: {
          id: expect.any(String),
          provider: type,
        },
      },
    });
  });

  it('POST /check', async () => {
    const response = await testRequest<{ valid?: boolean; code?: number }[]>({
      url: url(`check`),
      method: 'POST',
      payload: {
        payload: {
          address,
          type: 'EVMBulkVerify',
          types: generateEVMProviders(3),
          version,
        },
      },
    });

    expect(response).toHaveStatus(200);
    expect(response.data.length).toBe(3);

    // Valid or unauthorized is fine, no server or request errors
    response.data.forEach(({ valid, code }) => expect(valid || code === 403).toBeTruthy());
  });

  it('GET /health', async () => {
    const response = await testRequest({
      url: IAM_BASE_URL + '/health',
      method: 'GET',
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      message: 'Ok',
      date: expect.any(String),
    });
  });
});

describe('IAM (NFT)', () => {
  let address: string;
  let did: DID;

  beforeAll(async () => {
    const nftHolderPrivateKey = process.env.NFT_HOLDER_PRIVATE_KEY!;
    const wallet = new Wallet(nftHolderPrivateKey);
    ({ did, address } = await PassportUIUser.createFromWallet(wallet));
  });

  it('POST /eas/passport', async () => {
    const type = 'NFT';

    const challengeResponse = await testRequest<{
      credential?: { credentialSubject?: { challenge?: unknown } };
    }>({
      url: url(`challenge`),
      method: 'POST',
      payload: {
        payload: {
          address,
          type,
        },
      },
    });

    expect(challengeResponse).toHaveStatus(200);

    const challenge = challengeResponse.data.credential;
    const challengeMessage = challenge?.credentialSubject?.challenge;

    expect(challengeMessage).toBeDefined();

    const signedChallenge = await createSignedPayload(did, challengeMessage);

    const verifyResponse = await testRequest<{ credential: unknown }>({
      url: url(`verify`),
      method: 'POST',
      payload: {
        challenge,
        signedChallenge,
        payload: {
          address,
          type,
          signatureType: 'EIP712',
          version,
          proofs: {
            valid: 'true',
            username: 'test',
            signature: 'pass',
          },
        },
      },
    });

    expect(verifyResponse).toHaveStatus(200);
    expect(verifyResponse.data).toMatchObject({
      record: {
        type,
      },
      credential: {
        credentialSubject: {
          id: expect.any(String),
          provider: type,
        },
      },
    });

    const credential = verifyResponse.data.credential;

    expect(credential).toBeDefined();

    const nonce = '123';

    const createAttestationResponse = await testRequest({
      url: url(`eas/passport`),
      method: 'POST',
      payload: {
        chainIdHex: '0xa',
        nonce,
        recipient: address,
        credentials: [credential],
      },
    });

    expect(createAttestationResponse).toHaveStatus(200);
    expect(createAttestationResponse.data).toMatchObject({
      passport: {
        multiAttestationRequest: expect.any(Array),
        nonce: parseInt(nonce),
        fee: expect.any(String),
      },
      signature: {
        v: expect.any(Number),
        r: expect.any(String),
        s: expect.any(String),
      },
      invalidCredentials: [],
    });
  });
});
