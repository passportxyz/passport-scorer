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

  it("should render the scorer dashboard", async () => {
    await act(() => mockRouter.push("/dashboard/scorer"));

    const { getByText } = render(
      <TabRoute authenticationStatus="authenticated" />
    );

    await waitFor(() =>
      expect(getByText("Create a Scorer")).toBeInTheDocument()
    );
  });

  it("should show API key content when tab is clicked", async () => {
    await act(() => mockRouter.push("/dashboard/scorer"));

    const { getAllByText, getByText } = render(
      <TabRoute authenticationStatus="authenticated" />
    );
    const apiKeyElements = getAllByText("API Keys");
    expect(apiKeyElements.length).toBe(2);
    const apiKeyTab = apiKeyElements[1];

    fireEvent.click(apiKeyTab);

    expect(mockRouter).toMatchObject({
      asPath: "/dashboard/api-keys",
      pathname: "/dashboard/[tabRoute]",
      query: { tabRoute: "api-keys" },
    });
    await waitFor(() => expect(getByText("Create a key")).toBeInTheDocument());
  });
});
