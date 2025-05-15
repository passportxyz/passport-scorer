import { HeaderKeyAuth } from "../auth/strategies";
import { AuthStrategy } from "../types";
import { testRequest } from "../utils/testRequest";
import { InternalAPIUser, PassportUIUser, RegistryAPIUser } from "../users";
import { generateStamps } from "../generate";
import { DID } from "dids";
import { Wallet } from "ethers";
import { createSignedPayload } from "../utils/dids";

const url = (subpath: string) => process.env.INTERNAL_SCORER_API_BASE_URL + "/internal/" + subpath;

describe("Internal Requests", () => {
  let authStrategy: AuthStrategy;
  let didStr: string;
  let address: string;
  let scorerId: string;
  let customProviderId: string;
  let allowListName: string;

  beforeAll(async () => {
    let apiSecret: string;
    ({ apiSecret, scorerId } = await InternalAPIUser.get());
    authStrategy = new HeaderKeyAuth({ key: apiSecret });

    let did: DID;
    ({ address, allowListName, customProviderId, did } = await PassportUIUser.get());
    didStr = did.toString();
  });

  it("GET /score/v2/{scorer_id}/{address}", async () => {
    const response = await testRequest({
      url: url(`score/v2/${scorerId}/${address}`),
      method: "GET",
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      address,
      score: expect.any(String),
    });
  });

  it("POST /check-bans", async () => {
    const response = await testRequest({
      url: url("check-bans"),
      method: "POST",
      payload: [
        {
          credentialSubject: {
            hash: "test-hash",
            provider: "Twitter",
            id: didStr,
          },
        },
        {
          credentialSubject: {
            hash: "test-hash-2",
            provider: "GitHub",
            id: didStr,
          },
        },
      ],
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject([
      {
        hash: "test-hash",
        is_banned: expect.any(Boolean),
      },
      {
        hash: "test-hash-2",
        is_banned: expect.any(Boolean),
      },
    ]);
  });

  it("POST /check-revocations", async () => {
    const response = await testRequest({
      url: url("check-revocations"),
      method: "POST",
      payload: { proof_values: ["test-proof-value", "test-proof-value-2"] },
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject([
      {
        proof_value: "test-proof-value",
        is_revoked: expect.any(Boolean),
      },
      {
        proof_value: "test-proof-value-2",
        is_revoked: expect.any(Boolean),
      },
    ]);
  });

  it("GET /stake/gtc/{address}", async () => {
    const response = await testRequest({
      url: url(`stake/gtc/${address}`),
      method: "GET",
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      items: expect.any(Array),
    });
  });

  it("GET /stake/legacy-gtc/{address}/{round_id}", async () => {
    const response = await testRequest({
      url: url(`stake/legacy-gtc/${address}/1`),
      method: "GET",
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({ results: expect.any(Array) });
  });

  it("GET /cgrants/contributor_statistics", async () => {
    const response = await testRequest({
      url: url("cgrants/contributor_statistics"),
      method: "GET",
      payload: {
        address,
      },
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      num_grants_contribute_to: expect.any(Number),
      total_contribution_amount: expect.any(Number),
    });
  });

  it("GET /allow-list/{list}/{address}", async () => {
    const response = await testRequest({
      url: url(`allow-list/${allowListName}/${address}`),
      method: "GET",
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      is_member: expect.any(Boolean),
    });
  });

  it("GET /customization/credential/{provider_id}", async () => {
    const response = await testRequest({
      url: url(`customization/credential/${encodeURIComponent(customProviderId)}`),
      method: "GET",
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      ruleset: expect.objectContaining({
        name: customProviderId.split("#")[1],
      }),
    });
  });

  it("GET /embed/weights", async () => {
    const response = await testRequest({
      url: url("embed/weights"),
      method: "GET",
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(typeof response.data).toBe("object");
  });

  it("GET /embed/weights with community_id", async () => {
    const response = await testRequest({
      url: url("embed/weights"),
      method: "GET",
      payload: { community_id: scorerId },
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(typeof response.data).toBe("object");
  });
});

describe("Internal Requests (DID API Key)", () => {
  let authStrategy: AuthStrategy;

  beforeAll(async () => {
    const { apiKey } = await RegistryAPIUser.get();
    authStrategy = new HeaderKeyAuth({ key: apiKey, header: "X-API-Key" });
  });

  it("GET /embed/validate-api-key", async () => {
    const response = await testRequest({
      url: url("embed/validate-api-key"),
      method: "GET",
      authStrategy,
    });
    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      embed_rate_limit: expect.any(String),
    });
  });
});

const version = "0.0.0";
const iamUrl = (subpath: string) => process.env.IAM_BASE_URL + "/api/v" + version + "/" + subpath;

describe("Internal Requests (NFT Holder)", () => {
  let authStrategy: AuthStrategy;
  let did: DID;
  let address: string;
  let scorerId: string;

  beforeAll(async () => {
    let apiSecret: string;
    ({ apiSecret, scorerId } = await InternalAPIUser.get());
    authStrategy = new HeaderKeyAuth({ key: apiSecret });

    const nftHolderPrivateKey = process.env.NFT_HOLDER_PRIVATE_KEY!;
    const wallet = new Wallet(nftHolderPrivateKey);
    ({ did, address } = await PassportUIUser.createFromWallet(wallet));
  });

  it("POST /embed/stamps/{address}", async () => {
    const type = "NFT";

    const challengeResponse = await testRequest<{
      credential?: { credentialSubject?: { challenge?: unknown } };
    }>({
      url: iamUrl(`challenge`),
      method: "POST",
      payload: {
        payload: {
          address,
          type,
          signatureType: "EIP712",
        },
      },
    });

    expect(challengeResponse).toHaveStatus(200);

    const challenge = challengeResponse.data.credential;
    const challengeMessage = challenge?.credentialSubject?.challenge;

    expect(challengeMessage).toBeDefined();

    const signedChallenge = await createSignedPayload(did, challengeMessage);

    const verifyResponse = await testRequest<{ credential: unknown }[]>({
      url: iamUrl(`verify`),
      method: "POST",
      payload: {
        challenge,
        signedChallenge,
        payload: {
          address,
          type,
          types: [type],
          signatureType: "EIP712",
          version,
          proofs: {
            valid: "true",
            username: "test",
            signature: "pass",
          },
        },
      },
    });

    expect(verifyResponse).toHaveStatus(200);
    expect(verifyResponse.data[0]).toMatchObject({
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

    const credential = verifyResponse.data[0].credential;

    const response = await testRequest({
      url: url(`embed/stamps/${address}`),
      method: "POST",
      payload: {
        scorer_id: scorerId,
        stamps: [credential],
      },
      authStrategy,
    });

    expect(response).toHaveStatus(200);
    expect(response.data).toMatchObject({
      success: true,
      stamps: expect.any(Array),
      score: expect.objectContaining({
        address,
        score: expect.any(String),
      }),
    });
  });
});
