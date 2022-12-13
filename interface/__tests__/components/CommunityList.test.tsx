import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CommunityList from "../../components/CommunityList";
import { getCommunities, createCommunity } from "../../utils/account-requests";

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
  beforeEach(() => {
    (getCommunities as jest.Mock).mockResolvedValue([
      { name: "banks", description: "No bankd" },
      { name: "wells fargo", description: "WellsFargo" },
    ]);
    (createCommunity as jest.Mock).mockResolvedValue({});
  });
  it("should create a community", async () => {
    const sampleInput = {
      name: "name value",
      description: "description value",
    };
    render(<CommunityList />);

    await waitFor(async () => {
      const modalButton = screen.getByTestId("open-community-modal");
      fireEvent.click(modalButton as HTMLElement);
      expect(screen.getByTestId("create-button")).toBeInTheDocument();
      const nameInput = screen.getByTestId("community-name-input");
      const descriptionInput = screen.getByTestId(
        "community-description-input"
      );
      fireEvent.change(nameInput, { target: { value: sampleInput.name } });
      fireEvent.change(descriptionInput, {
        target: { value: sampleInput.description },
      });
      const createButton = screen.getByTestId("create-button");
      fireEvent.click(createButton as HTMLElement);
      expect(createCommunity).toHaveBeenCalledWith(sampleInput);
    });
  });

  it("should render a list of communities", async () => {
    render(<CommunityList />);

    await waitFor(async () => {
      expect(screen.getByText("banks")).toBeInTheDocument();
    });
  });
});
