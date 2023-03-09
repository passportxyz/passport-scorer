import { act, fireEvent, render, waitFor } from "@testing-library/react";
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
    (getCommunities as jest.Mock).mockResolvedValue([
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
    (getApiKeys as jest.Mock).mockResolvedValue([]);
    (updateCommunity as jest.Mock).mockResolvedValue(undefined);
    (deleteCommunity as jest.Mock).mockResolvedValue(undefined);
  });

  it("should render all the scorers returned by the backend", async () => {
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
    await act(() => mockRouter.push("/dashboard/scorer"));

    const { getByText, getByTestId } = render(
      <TabRoute authenticationStatus="authenticated" />
    );

    await waitFor(() =>
      expect(getByText("Create a Scorer")).toBeInTheDocument()
    );

    await waitFor(() => expect(getByText("Test Scorer 1")).toBeInTheDocument());

    console.log(getByText("Test Scorer 1"));

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
    act(() => {
      saveChangeBtn.click();
    });

    expect((updateCommunity as jest.Mock).mock.calls).toHaveLength(1);
  });

//   it("should make an delete request to the scorer when user initiates a delete", async () => {
//     await act(() => mockRouter.push("/dashboard/scorer"));

//     const { getByText, getByTestId } = render(
//       <TabRoute authenticationStatus="authenticated" />
//     );

//     await waitFor(() =>
//       expect(getByText("Create a Scorer")).toBeInTheDocument()
//     );

//     await waitFor(() => expect(getByText("Test Scorer 1")).toBeInTheDocument());

//     console.log(getByText("Test Scorer 1"));

//     const scorerItem = getByTestId("scorer-item-1");
//     const menuButton = scorerItem.querySelector(
//       '[data-testid="card-menu-button"]'
//     );

//     expect(menuButton).toBeInTheDocument();

//     if (menuButton) {
//       act(() => {
//         menuButton.click();
//       });
//     }

//     await waitFor(() => expect(getByTestId("menu-delete-1")).toBeVisible());

//     const deleteMenuItem = getByTestId("menu-delete-1");
//     act(() => {
//       deleteMenuItem.click();
//     });

//     await waitFor(() => expect(getByText("Are you sure?")).toBeVisible());

//     const confirmDeletionBtn = getByText("Confirm Deletion");
//     act(() => {
//       confirmDeletionBtn.click();
//     });

//     expect((deleteCommunity as jest.Mock).mock.calls).toHaveLength(1);
//   });
});
