import { HeaderKeyAuth } from "../auth/strategies";
import { AuthStrategy } from "../types";
import { testRequest } from "../utils/testRequest";
import { InternalAPIUser, PassportUIUser } from "../users";

const url = (subpath: string) => process.env.INTERNAL_SCORER_API_BASE_URL + "/internal/" + subpath;

describe("Internal Requests (Credential Checks)", () => {
  let authStrategy: AuthStrategy;
  let address: string;
  let customProviderId: string;
  let allowListName: string;

  beforeAll(async () => {
    const { apiSecret } = await InternalAPIUser.get();
    authStrategy = new HeaderKeyAuth({ key: apiSecret });

    ({ address, allowListName, customProviderId } = await PassportUIUser.get());
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
});
