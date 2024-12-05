import axios, { isAxiosError } from 'axios';
import { DID } from 'dids';
import { Cacao } from '@didtools/cacao';
import { Authenticate, TestRequestOptionsNoAuth } from '../../types';

interface DidSignAuthConfig {
  did: DID;
  ceramicCacheEndpoint?: string;
  retryAttempts?: number;
}

export const didSignAuth = ({ did }: DidSignAuthConfig): Authenticate => {
  // Cache accessToken after first retrieval
  let accessToken: string;

  return async (options: TestRequestOptionsNoAuth): Promise<TestRequestOptionsNoAuth> => {
    if (!accessToken) {
      accessToken = await getAccessToken(did);
    }

    // Add to Authorization header
    return {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Bearer ${accessToken}`,
      },
    };
  };
};

const getAccessToken = async (did: DID) => {
  console.log('Getting access token for did:', did.parent);

  // Get nonce from Scorer API
  let nonce: string;

  try {
    const nonceResponse = await axios.get(`${process.env.SCORER_API_BASE_URL}/account/nonce`);
    nonce = nonceResponse.data.nonce;
  } catch (error) {
    if (isAxiosError(error)) {
      throw new Error(
        `Failed to get nonce from server: ${error.message}, status: ${error.response?.status}`
      );
    }
    throw error;
  }

  // Create signed payload
  const payloadToSign = { nonce };
  const payloadForVerifier = {
    ...(await createSignedPayload(did, payloadToSign)),
    nonce,
  };

  // Authenticate and get access token
  let accessToken: string;
  try {
    const authResponse = await axios.post(
      `${process.env.SCORER_API_BASE_URL}/ceramic-cache/authenticate`,
      payloadForVerifier
    );
    accessToken = authResponse.data?.access as string;
  } catch (error) {
    if (isAxiosError(error)) {
      throw new Error(
        `Failed to authenticate user with did: ${did.parent}: ${error.message}, status: ${error.response?.status}`
      );
    }
    throw error;
  }

  if (!accessToken) {
    throw new Error('No access token received from authentication');
  }

  return accessToken;
};

// Helper function to create signed payload
const createSignedPayload = async (did: DID, data: any) => {
  const { jws, cacaoBlock } = await did.createDagJWS(data);

  if (!cacaoBlock) {
    throw new Error(`Failed to create DagJWS for did: ${did.parent}`);
  }

  const { link, payload, signatures } = jws;
  const cacao = await Cacao.fromBlockBytes(cacaoBlock);
  const issuer = cacao.p.iss;

  return {
    signatures,
    payload,
    cid: Array.from(link ? link.bytes : []),
    cacao: Array.from(cacaoBlock),
    issuer,
  };
};

// Usage example:
/*
// Create a test DID
const { did, seed } = await createTestDID();
console.log('Created DID with seed:', seed);

const authStrategy = didSignAuth({ 
  did,
  ceramicCacheEndpoint: 'https://custom.endpoint',
  retryAttempts: 3
});

const requestOptions = await authStrategy({
  url: 'https://api.example.com/endpoint',
  method: 'POST',
  payload: { ... }
});
*/
