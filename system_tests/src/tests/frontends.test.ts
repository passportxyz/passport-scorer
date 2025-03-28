import { testRequest } from "../utils/testRequest";

const DOMAIN = process.env.DOMAIN;

describe("Frontends", () => {
  it("GET Scorer UI", async () => {
    const response = await testRequest({
      url: `https://scorer.${DOMAIN}/`,
      method: "GET",
    });
    expect(response).toHaveStatus(200);
  });

  it("GET Passport UI", async () => {
    const response = await testRequest({
      url: `https://app.${DOMAIN}/`,
      method: "GET",
    });
    expect(response).toHaveStatus(200);
  });

  it("GET Passport UI", async () => {
    const response = await testRequest({
      url: `https://stake.${DOMAIN}/`,
      method: "GET",
    });
    expect(response).toHaveStatus(200);
  });
});
