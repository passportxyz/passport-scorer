import {
  act,
  fireEvent,
  render,
  waitFor,
  waitForElementToBeRemoved,
} from "@testing-library/react";
import TabRoute from "../../pages/dashboard/[...tabRoute]";
import mockRouter from "next-router-mock";
import { createDynamicRouteParser } from "next-router-mock/dynamic-routes";
import {
  getCommunities,
  getApiKeys,
  updateCommunity,
  deleteCommunity,
} from "../../utils/account-requests";
import { click } from "@testing-library/user-event/dist/types/setup/directApi";

jest.mock("../../utils/account-requests.ts", () => ({
  getCommunities: jest.fn(),
  getApiKeys: jest.fn(),
  updateCommunity: jest.fn(),
  deleteCommunity: jest.fn(),
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

describe("Dashboard Scorer", () => {
  beforeEach(() => {
    (deleteCommunity as jest.Mock).mockResolvedValue(undefined);
  });

  it("should render all the scorers returned by the backend", async () => {
    (getCommunities as jest.Mock).mockClear().mockResolvedValue([
      // give me an iso datetime string for testing
      {
        id: 1,
        name: "Test Scorer 1",
        description: "Test 1 Description",
        created_at: "2021-01-10T00:00:00.000Z",
        use_case: "Airdrop Protection",
      },
      {
        id: 2,
        name: "Test Scorer 2",
        description: "Test 2 Description",
        created_at: "2021-01-10T00:00:00.000Z",
        use_case: "Airdrop Protection",
      },
      {
        id: 3,
        name: "Test Scorer 3",
        description: "Test 3 Description",
        created_at: "2021-01-10T00:00:00.000Z",
        use_case: "Airdrop Protection",
      },
    ]);

    await act(() => mockRouter.push("/dashboard/scorer"));

    const { getByText } = render(
      <TabRoute authenticationStatus="authenticated" />
    );

    await waitFor(() =>
      expect(getByText("Create a Scorer")).toBeInTheDocument()
    );
    await waitFor(() => expect(getByText("Test Scorer 1")).toBeInTheDocument());
    await waitFor(() => expect(getByText("Test Scorer 2")).toBeInTheDocument());
    await waitFor(() => expect(getByText("Test Scorer 3")).toBeInTheDocument());
  });

  it("should make an update request to the scorer when user initiates a change", async () => {
    const promise = Promise.resolve();
    const communitiesPromises: Promise<any>[] = [];

    // This is a list of mock data. We'll pop an element form the list for each
    // invocation of getCommunities
    const scorerLists = [
      [
        // give me an iso datetime string for testing
        {
          id: 1,
          name: "Test Scorer 1",
          description: "Test 1 Description",
          created_at: "2021-01-10T00:00:00.000Z",
          use_case: "Airdrop Protection",
        },
      ],
      [
        // give me an iso datetime string for testing
        {
          id: 1,
          name: "Test Scorer 2",
          description: "Test 2 Description",
          created_at: "2021-01-10T00:00:00.000Z",
          use_case: "Airdrop Protection",
        },
      ],
    ];

    (getCommunities as jest.Mock).mockClear().mockImplementation(() => {
      const scorerList = scorerLists.shift();
      const communitiesPromise = Promise.resolve(scorerList);
      communitiesPromises.push(communitiesPromise);
      return communitiesPromise;
    });

    (updateCommunity as jest.Mock)
      .mockClear()
      .mockImplementation(() => promise);

    await act(() => mockRouter.push("/dashboard/scorer"));

    const { getByText, getByTestId } = render(
      <TabRoute authenticationStatus="authenticated" />
    );

    await waitFor(() =>
      expect(getByText("Create a Scorer")).toBeInTheDocument()
    );

    await waitFor(() => expect(getByText("Test Scorer 1")).toBeInTheDocument());

    const scorerItem = getByTestId("scorer-item-1");
    const menuButton = scorerItem.querySelector(
      '[data-testid="card-menu-button"]'
    );

    expect(menuButton).toBeInTheDocument();

    if (menuButton) {
      act(() => {
        menuButton.click();
      });
    }

    await waitFor(() => expect(getByTestId("menu-rename-1")).toBeVisible());

    const renameMenuItem = getByTestId("menu-rename-1");
    act(() => {
      renameMenuItem.click();
    });

    await waitFor(() => expect(getByText("Rename Scorer")).toBeVisible());

    const saveChangeBtn = getByText("Save Changes");
    act(() => saveChangeBtn.click());

    // Make sure new results are pulled from the server
    await waitFor(() => expect(getByText("Test Scorer 2")).toBeInTheDocument());

    expect((updateCommunity as jest.Mock).mock.calls).toHaveLength(1);
    expect((getCommunities as jest.Mock).mock.calls).toHaveLength(2);
  });

  it("should make a delete request to the scorer when user initiates a delete", async () => {
    const promise = Promise.resolve();
    const communitiesPromises: Promise<any>[] = [];

    // This is a list of mock data. We'll pop an element form the list for each
    // invocation of getCommunities
    const scorerLists = [
      [
        {
          id: 1,
          name: "Test Scorer 1",
          description: "Test 1 Description",
          created_at: "2021-01-10T00:00:00.000Z",
          use_case: "Airdrop Protection",
        },
      ],
      // Empty list for after the delete
      [],
    ];

    (getCommunities as jest.Mock).mockClear().mockImplementation(() => {
      const scorerList = scorerLists.shift();
      const communitiesPromise = Promise.resolve(scorerList);
      communitiesPromises.push(communitiesPromise);
      return communitiesPromise;
    });

    (updateCommunity as jest.Mock)
      .mockClear()
      .mockImplementation(() => promise);

    await act(() => mockRouter.push("/dashboard/scorer"));

    const { getByText, getByTestId } = render(
      <TabRoute authenticationStatus="authenticated" />
    );

    await waitFor(() =>
      expect(getByText("Create a Scorer")).toBeInTheDocument()
    );

    await waitFor(() => expect(getByText("Test Scorer 1")).toBeInTheDocument());

    const scorerItem = getByTestId("scorer-item-1");
    const menuButton = scorerItem.querySelector(
      '[data-testid="card-menu-button"]'
    );

    expect(menuButton).toBeInTheDocument();

    if (menuButton) {
      act(() => {
        menuButton.click();
      });
    }

    await waitFor(() => expect(getByTestId("menu-delete-1")).toBeVisible());

    const deleteMenuItem = getByTestId("menu-delete-1");
    act(() => {
      deleteMenuItem.click();
    });

    await waitFor(() => expect(getByText("Are you sure?")).toBeVisible());

    const confirmDeletionBtn = getByText("Confirm Deletion");
    act(() => {
      confirmDeletionBtn.click();
    });

    // Make sure the empty page is displayed
    await waitFor(() =>
      expect(getByText("Create a Scorer")).toBeInTheDocument()
    );

    expect((deleteCommunity as jest.Mock).mock.calls).toHaveLength(1);
    expect((getCommunities as jest.Mock).mock.calls).toHaveLength(2);
  });
});
