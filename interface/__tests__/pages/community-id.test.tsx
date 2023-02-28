import { fireEvent, screen, render, waitFor } from "@testing-library/react";
import TabRoute from "../../pages/dashboard/[...tabRoute]";
import {
  getCommunityScorers,
  updateCommunityScorers,
} from "../../utils/account-requests";

// mock header component
jest.mock("../../components/Header", () => {
  // eslint-disable-next-line react/display-name
  return () => <div></div>;
});

// mock next router
jest.mock("next/router", () => ({
  useRouter: () => ({
    pathname: "/dashboard/scorer/2",
    query: { tabRoute: ["scorer", "2"] },
  }),
}));

jest.mock("../../utils/account-requests.ts", () => ({
  getCommunityScorers: jest.fn(),
  updateCommunityScorers: jest.fn(),
}));

const scorerResponse = {
  scorers: [
    {
      id: "WEIGHTED",
      label: "Weighted",
    },
    {
      id: "WEIGHTED_BINARY",
      label: "Weighted Binary",
    },
  ],
  currentScorer: "WEIGHTED",
};

describe("Dashboard", () => {
  it("Should render a list of scorer options", async () => {
    (getCommunityScorers as jest.Mock).mockResolvedValue(scorerResponse);
    render(<TabRoute />);
    await waitFor(async () => {
      expect(screen.getByText("Weighted")).toBeInTheDocument();
      expect(screen.getByText("Weighted Binary")).toBeInTheDocument();
    });
  });
  it("should update active radio button when selected", async () => {
    (getCommunityScorers as jest.Mock).mockResolvedValue(scorerResponse);
    const { container } = render(<TabRoute />);

    waitFor(async () => {
      const radio = container.querySelector(
        `input[value="${scorerResponse.scorers[1].id}"]`
      );

      fireEvent.change(radio as HTMLElement);
      expect(radio).toHaveAttribute("checked");
      expect(updateCommunityScorers).toHaveBeenCalledWith(
        "2",
        scorerResponse.scorers[1].id
      );
    });
  });
});
