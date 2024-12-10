import { testRequest } from '../utils/testRequest';
import { PassportUIUser } from '../users';
import { DID } from 'dids';
import { createSignedPayload } from '../utils/dids';

const url = (subpath: string, version?: '0.0.0') =>
  process.env.IAM_BASE_URL + '/api/v' + version + '/' + subpath;

describe('IAM', () => {
  const version = '0.0.0';
  let address: string;
  let did: DID;

  beforeAll(async () => {
    ({ did, address } = await PassportUIUser.get());
  });

  it('POST /verify (Simple credential)', async () => {
    const type = 'Simple';

    const challengeResponse = await testRequest<{
      credential?: { credentialSubject?: { challenge?: unknown } };
    }>({
      url: url(`challenge`, version),
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
      url: url(`verify`, version),
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
});
