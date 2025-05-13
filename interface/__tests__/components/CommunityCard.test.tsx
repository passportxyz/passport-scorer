import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CommunityList from "../../components/CommunityList";
import CommunityCard from "../../components/CommunityCard";
import {
  getCommunities,
  createCommunity,
  updateCommunity,
  deleteCommunity,
} from "../../utils/account-requests";

jest.mock("../../utils/account-requests.ts", () => ({
  getCommunities: jest.fn(),
  createCommunity: jest.fn(),
}));

describe("CommunityCard", () => {
  beforeEach(() => {
    (getCommunities as jest.Mock).mockResolvedValue([
      { name: "banks", description: "No bankd" },
      { name: "wells fargo", description: "WellsFargo" },
    ]);
    (createCommunity as jest.Mock).mockResolvedValue({});
  });

  it("should render a single community with a delete button", async () => {
    // render(<CommunityCard />);
    // await waitFor(async () => {
    //   expect(screen.getByText("banks")).toBeInTheDocument();
    // });
  });

  it("should render a single community with a edit button", async () => {
    // render(<CommunityCard />);
    // await waitFor(async () => {
    //   expect(screen.getByText("banks")).toBeInTheDocument();
    // });
  });

  it("should show an error and disable save if threshold is not greater than 0", async () => {
    const mockCommunity = {
      id: 1,
      name: "Test Community",
      description: "Test Description",
      created_at: "2021-01-10T00:00:00.000Z",
      use_case: "Airdrop Protection",
      threshold: 20,
      rule: "LIFO",
      scorer: "WEIGHTED",
    };
    const handleUpdateCommunity = jest.fn();
    const handleDeleteCommunity = jest.fn();
    render(
      <CommunityCard
        community={mockCommunity}
        onCommunityDeleted={jest.fn()}
        handleUpdateCommunity={handleUpdateCommunity}
        handleDeleteCommunity={handleDeleteCommunity}
      />
    );

    // Open the edit modal
    const menuButton = await screen.findByTestId("card-menu-button");
    fireEvent.click(menuButton);
    const editButton = await screen.findByTestId("menu-rename-1");
    fireEvent.click(editButton);

    // Wait for modal
    await waitFor(() => screen.getByText("Edit Scorer"));

    // Find threshold input and set to 0
    const thresholdInput = screen.getByTestId("use-case-threshold-input");
    fireEvent.change(thresholdInput, { target: { value: "0" } });
    expect(await screen.findByTestId("threshold-error")).toHaveTextContent(
      "Threshold must be greater than 0"
    );
    const saveButton = screen.getByText("Save Changes");
    expect(saveButton).toBeDisabled();

    // Set to negative value
    fireEvent.change(thresholdInput, { target: { value: "-5" } });
    expect(await screen.findByTestId("threshold-error")).toHaveTextContent(
      "Threshold must be greater than 0"
    );
    expect(saveButton).toBeDisabled();

    // Set to empty
    fireEvent.change(thresholdInput, { target: { value: "" } });
    expect(await screen.findByTestId("threshold-error")).toHaveTextContent(
      "Threshold must be greater than 0"
    );
    expect(saveButton).toBeDisabled();

    // Set to valid value
    fireEvent.change(thresholdInput, { target: { value: "10" } });
    await waitFor(() => {
      expect(screen.queryByTestId("threshold-error")).toBeNull();
      expect(saveButton).not.toBeDisabled();
    });
  });
});
