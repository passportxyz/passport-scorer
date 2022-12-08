import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CommunityList from "../../components/CommunityList";
import CommunityCard from "../../components/CommunityCard";
import { getCommunities, createCommunity, updateCommunity, deleteCommunity } from "../../utils/account-requests";

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
});