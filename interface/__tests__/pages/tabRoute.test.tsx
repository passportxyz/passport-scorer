import { act, fireEvent, render, waitFor } from "@testing-library/react";
import TabRoute from "../../pages/dashboard/[...tabRoute]";
import mockRouter from "next-router-mock";
import { createDynamicRouteParser } from "next-router-mock/dynamic-routes";
import { getCommunities, getApiKeys } from "../../utils/account-requests";

jest.mock("../../utils/account-requests.ts", () => ({
  getCommunities: jest.fn(),
  getApiKeys: jest.fn(),
}));

mockRouter.useParser(
  createDynamicRouteParser([
    // These paths should match those found in the `/pages` folder:
    "/dashboard/[tabRoute]",
  ])
);

jest.mock("next/router", () => require("next-router-mock"));

jest.mock("@rainbow-me/rainbowkit", () => {
  return {
    ConnectButton: jest.fn(() => <div>ConnectButton</div>),
  };
});

describe("Dashboard", () => {
  beforeEach(() => {
    (getCommunities as jest.Mock).mockResolvedValue([
      { name: "Test", description: "Test" },
    ]);
    (getApiKeys as jest.Mock).mockResolvedValue([]);
  });

  it("should render the community dashboard", async () => {
    await act(() => mockRouter.push("/dashboard/community"));

    const { getByText } = render(
      <TabRoute authenticationStatus="authenticated" />
    );

    await waitFor(() =>
      expect(getByText("My Communities")).toBeInTheDocument()
    );
  });

  it("should show API key content when tab is clicked", async () => {
    await act(() => mockRouter.push("/dashboard/community"));

    const { getByText } = render(
      <TabRoute authenticationStatus="authenticated" />
    );
    const apiKeyTab = getByText("API Keys");
    fireEvent.click(apiKeyTab);

    expect(mockRouter).toMatchObject({
      asPath: "/dashboard/api-keys",
      pathname: "/dashboard/[tabRoute]",
      query: { tabRoute: "api-keys" },
    });
    await waitFor(() => expect(getByText("Create a key")).toBeInTheDocument());
  });
});
