import axios, { isAxiosError } from 'axios';
import { DID } from 'dids';
import { Cacao } from '@didtools/cacao';
import { TestRequestOptionsNoAuth } from '../../types';
import { BaseAuthStrategy } from './strategy';

interface DidSignAuthConfig {
  did: DID;
}

export class DidSignAuth extends BaseAuthStrategy {
  did: DID;
  accessToken?: string;

  constructor({ did }: DidSignAuthConfig) {
    super({ name: 'did-sign-auth' });
    this.did = did;
  }

  async applyAuth(options: TestRequestOptionsNoAuth): Promise<TestRequestOptionsNoAuth> {
    if (!this.accessToken) {
      this.accessToken = await getAccessToken(this.did);
    }

    return {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Bearer ${this.accessToken}`,
      },
    };
  }
}

const getAccessToken = async (did: DID) => {
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
