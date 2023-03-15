import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CommunityList from "../../components/CommunityList";
import { getCommunities } from "../../utils/account-requests";

jest.mock("../../utils/account-requests.ts", () => ({
  getCommunities: jest.fn(),
  createCommunity: jest.fn(),
}));

// mock next router
jest.mock("next/router", () => ({
  useRouter: () => ({
    pathname: "/dashboard/api-keys",
  }),
}));

describe("CommunityList", () => {
  it("should open the use-case modal after clicking the `+ Scorer` button", async () => {
    render(<CommunityList />);
    expect(screen.getByTestId("no-values-add")).toBeInTheDocument();

    const modalButton = screen.getByTestId("no-values-add");
    fireEvent.click(modalButton as HTMLElement);

    // Verify that the first step of the modal is shown
    await waitFor(async () =>
      expect(screen.getByText("Select a Use Case")).toBeInTheDocument()
    );

    // expect(screen.getByTestId("create-button")).toBeInTheDocument();
    // const nameInput = screen.getByTestId("community-name-input");
    // const descriptionInput = screen.getByTestId("community-description-input");
    // fireEvent.change(nameInput, { target: { value: sampleInput.name } });
    // fireEvent.change(descriptionInput, {
    //   target: { value: sampleInput.description },
    // });
    // const createButton = screen.getByTestId("create-button");
    // fireEvent.click(createButton as HTMLElement);
    // expect(createCommunity).toHaveBeenCalledWith(sampleInput);
    // waitForElementToBeRemoved(screen.getByTestId("community-modal"));
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
      render(<CommunityList />);

      await waitFor(async () => {
        expect(screen.getByText("banks")).toBeInTheDocument();
      });
    });
  });
});
