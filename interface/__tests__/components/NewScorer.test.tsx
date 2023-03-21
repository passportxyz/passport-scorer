import {
  act,
  fireEvent,
  render,
  waitFor,
  screen,
} from "@testing-library/react";
import NewScorer from "../../components/NewScorer";
import mockRouter from "next-router-mock";
import { createDynamicRouteParser } from "next-router-mock/dynamic-routes";
import { createCommunity } from "../../utils/account-requests";

// TODO temporary placeholder to let this compile until these tests are fixed
// Should probably render within a mock router
const NewScorerRoute = () => {
  return <NewScorer />;
};

jest.mock("../../utils/account-requests.ts", () => ({
  createCommunity: jest.fn(),
}));

mockRouter.useParser(
  createDynamicRouteParser([
    // These paths should match those found in the `/pages` folder:
    "/dashboard/[tabRoute]",
  ])
);

jest.mock("next/router", () => require("next-router-mock"));

const localStorageMock = (function () {
  let store: any = {};

  return {
    getItem(key: any) {
      return store[key];
    },

    setItem(key: any, value: any) {
      store[key] = value;
    },

    clear() {
      store = {};
    },

    removeItem(key: any) {
      delete store[key];
    },

    getAll() {
      return store;
    },
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("NewScorerRoute", () => {
  beforeEach(() => {
    (createCommunity as jest.Mock).mockResolvedValue([
      { name: "Test", description: "Test" },
    ]);

    localStorageMock.setItem(
      "tempScorer",
      JSON.stringify({
        useCase: 0, // 0 = Airdrop Protection
        name: "Gitcoin Airdrop",
        description:
          "This airdrop is for participants of the Gitcoin hackathon",
      })
    );
  });

  it.skip("should render the scoring mechanism page with localstorage items from use case modal", async () => {
    render(<NewScorerRoute />);

    expect(screen.getByText("Select a Scoring Mechanism")).toBeInTheDocument();
    expect(screen.getByText("Airdrop Protection")).toBeInTheDocument();
    expect(screen.getByText("Gitcoin Airdrop")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This airdrop is for participants of the Gitcoin hackathon"
      )
    ).toBeInTheDocument();
  });

  it.skip("continue button should only be enabled when a scoring mechanism is selected", async () => {
    render(<NewScorerRoute />);

    const scoringMechanism = screen.getByTestId("scoring-mechanism-0");
    const createScorerButton = screen
      .getByText(/Create Scorer/i)
      .closest("button");

    expect(createScorerButton).toBeDisabled();

    fireEvent.click(scoringMechanism as HTMLElement);

    expect(createScorerButton).toBeEnabled();
  });

  it.skip("should display cancel confirmation modal when cancel button is clicked", async () => {
    render(<NewScorerRoute />);

    const cancelButton = screen.getByText(/Cancel/i).closest("button");

    fireEvent.click(cancelButton as HTMLElement);

    expect(screen.getByText("Are you sure?")).toBeInTheDocument();
    expect(
      screen.getByText(/Exit Scorer/i).closest("button")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Continue Editing/i).closest("button")
    ).toBeInTheDocument();
  });

  it.skip("should switch to dashboard route when scorer is exited", async () => {
    render(<NewScorerRoute />);

    const cancelButton = screen.getByText(/Cancel/i).closest("button");
    fireEvent.click(cancelButton as HTMLElement);

    const exitScorerButton = screen.getByText(/Exit Scorer/i).closest("button");
    fireEvent.click(exitScorerButton as HTMLElement);

    expect(mockRouter).toMatchObject({
      asPath: "/dashboard/scorer",
      pathname: "/dashboard/[tabRoute]",
      query: {},
    });
  });

  it.skip("should create new scorer when Create Scorer button is clicked", async () => {
    render(<NewScorerRoute />);

    const scoringMechanism = screen.getByTestId("scoring-mechanism-0"); // Weighted
    const createScorerButton = screen
      .getByText(/Create Scorer/i)
      .closest("button");

    fireEvent.click(scoringMechanism as HTMLElement);

    fireEvent.click(createScorerButton as HTMLElement);

    expect(createCommunity).toHaveBeenCalledWith({
      name: "Gitcoin Airdrop",
      description: "This airdrop is for participants of the Gitcoin hackathon",
      use_case: "Airdrop Protection",
      rule: "LIFO",
      scorer: "WEIGHTED",
    });

    await waitFor(() => {
      expect(mockRouter).toMatchObject({
        asPath: "/dashboard/scorer",
        pathname: "/dashboard/[tabRoute]",
        query: {},
      });
    });
  });
});
