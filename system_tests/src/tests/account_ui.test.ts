import { testRequest } from "../utils/testRequest";
import { PassportUIUser } from "../users";

const url = (subpath: string) => process.env.SCORER_API_BASE_URL + "/account/" + subpath;

describe("Account (Passport UI)", () => {
  let customizationPath: string;
  let customProviderId: string;

  beforeAll(async () => {
    ({ customizationPath, customProviderId } = await PassportUIUser.get());
  });

  it("GET /customization/{dashboard_path}", async () => {
    const response = await testRequest({
      url: url(`customization/${encodeURIComponent(customizationPath)}`),
      method: "GET",
    });

    expect(response).toHaveStatus(200);

    expect(response.data).toMatchObject({
      key: customizationPath,
    });
  });

  it("GET /customization/credential/{provider_id}", async () => {
    const response = await testRequest({
      url: url(`customization/credential/${encodeURIComponent(customProviderId)}`),
      method: "GET",
    });

    expect(response).toHaveStatus(200);

    expect(response.data).toMatchObject({
      ruleset: expect.objectContaining({
        name: customProviderId.split("#")[1],
      }),
    });
  });
});
