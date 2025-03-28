import { HeaderKeyAuth } from "../auth/strategies";
import { AuthStrategy } from "../types";
import { testRequest } from "../utils/testRequest";
import { InternalAPIUser, PassportUIUser } from "../users";

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + "/internal/" + subpath;

describe("Internal Requests", () => {
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

  it("GET /score/{scorer_id}/{address}", async () => {
    const response = await testRequest({
      url: url(`score/v2/${scorerId}/${address}`),
      method: "GET",
      authStrategy,
    });

    expect(response).toHaveStatus(200);
  });
});
