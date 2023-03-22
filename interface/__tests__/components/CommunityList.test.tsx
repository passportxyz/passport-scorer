import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react";
import CommunityList from "../../components/CommunityList";
import {
  getCommunities,
  createCommunity,
  updateCommunity,
  deleteCommunity,
} from "../../utils/account-requests";

jest.mock("../../utils/account-requests.ts", () => ({
  getCommunities: jest.fn(),
  createCommunity: jest.fn(),
  deleteCommunity: jest.fn(),
  updateCommunity: jest.fn(),
}));

describe("CommunityList", () => {
  it("should open the use-case modal after clicking the `+ Scorer` button", async () => {
    const { getByTestId, getByText } = render(<CommunityList />);
    expect(getByTestId("no-values-add")).toBeInTheDocument();

    const modalButton = getByTestId("no-values-add");
    fireEvent.click(modalButton as HTMLElement);

    // Verify that the first step of the modal is shown
    await waitFor(async () =>
      expect(getByText("Select a Use Case")).toBeInTheDocument()
    );

    // expect(getByTestId("create-button")).toBeInTheDocument();
    // const nameInput = getByTestId("community-name-input");
    // const descriptionInput = getByTestId("community-description-input");
    // fireEvent.change(nameInput, { target: { value: sampleInput.name } });
    // fireEvent.change(descriptionInput, {
    //   target: { value: sampleInput.description },
    // });
    // const createButton = getByTestId("create-button");
    // fireEvent.click(createButton as HTMLElement);
    // expect(createCommunity).toHaveBeenCalledWith(sampleInput);
    // waitForElementToBeRemoved(getByTestId("community-modal"));
  });

  describe("when the community list already has records", () => {
    beforeEach(() => {
      (getCommunities as jest.Mock).mockResolvedValue([
        { name: "banks", description: "No bankd" },
        { name: "wells fargo", description: "WellsFargo" },
      ]);
      // (createCommunity as jest.Mock).mockResolvedValue({});
    });

    it("should render a list of communities", async () => {
      const { getByText } = render(<CommunityList />);

      await waitFor(async () => {
        expect(getByText("banks")).toBeInTheDocument();
      });
    });
  });
});

describe("Dashboard Scorer", () => {
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

    const { getByText } = render(<CommunityList />);

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

    const { getByText, getByTestId } = render(<CommunityList />);

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
      fireEvent.click(menuButton as HTMLElement);
    }

    await waitFor(() => expect(getByTestId("menu-rename-1")).toBeVisible());

    const renameMenuItem = getByTestId("menu-rename-1");
    fireEvent.click(renameMenuItem as HTMLElement);

    await waitFor(() => expect(getByText("Rename Scorer")).toBeVisible());

    const saveChangeBtn = getByText("Save Changes");
    fireEvent.click(saveChangeBtn as HTMLElement);

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

    const { getByText, getByTestId } = render(<CommunityList />);

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
      fireEvent.click(menuButton as HTMLElement);
    }

    await waitFor(() => expect(getByTestId("menu-delete-1")).toBeVisible());

    const deleteMenuItem = getByTestId("menu-delete-1");
    fireEvent.click(deleteMenuItem as HTMLElement);

    await waitFor(() => expect(getByText("Are you sure?")).toBeVisible());

    const confirmDeletionBtn = getByText("Confirm Deletion");
    fireEvent.click(confirmDeletionBtn as HTMLElement);

    // Make sure the empty page is displayed
    await waitFor(() =>
      expect(getByText("Create a Scorer")).toBeInTheDocument()
    );

    expect((deleteCommunity as jest.Mock).mock.calls).toHaveLength(1);
    expect((getCommunities as jest.Mock).mock.calls).toHaveLength(2);
  });
});
