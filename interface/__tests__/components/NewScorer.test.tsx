import { fireEvent, waitFor, screen } from "@testing-library/react";
import { createCommunity } from "../../utils/account-requests";

import { renderApp } from "../../__test-fixtures__/appHelpers";

jest.mock("../../utils/account-requests.ts", () => ({
  createCommunity: jest.fn(),
  getCommunities: jest.fn(),
}));

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

const expectNavigateToDashboard = async () => {
  await waitFor(() => {
    expect(
      screen.getByText(
        "A Scorer is used to score Passports. An API key is required to access those scores."
      )
    ).toBeInTheDocument();
  });
};

describe("NewScorer", () => {
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

  it("should render the scoring mechanism page with localstorage items from use case modal", async () => {
    renderApp("/new-scorer");
    expect(screen.getByText("Select a Scoring Mechanism")).toBeInTheDocument();
    expect(screen.getByText("Airdrop Protection")).toBeInTheDocument();
    expect(screen.getByText("Gitcoin Airdrop")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This airdrop is for participants of the Gitcoin hackathon"
      )
    ).toBeInTheDocument();
  });

  it("continue button should only be enabled when a scoring mechanism is selected", async () => {
    renderApp("/new-scorer");

    const scoringMechanism = screen.getByTestId("scoring-mechanism-0");
    const createScorerButton = screen
      .getByText(/Create Scorer/i)
      .closest("button");

    expect(scoringMechanism).toBeInTheDocument();
    expect(createScorerButton).toBeDisabled();

    fireEvent.click(scoringMechanism as HTMLElement);

    await waitFor(() =>
      expect(screen.getByText(/Create Scorer/i).closest("button")).toBeEnabled()
    );
  });

  it("should display cancel confirmation modal when cancel button is clicked", async () => {
    renderApp("/new-scorer");

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

  it("should switch to dashboard route when scorer is exited", async () => {
    renderApp("/new-scorer");

    const cancelButton = screen.getByText(/Cancel/i).closest("button");
    fireEvent.click(cancelButton as HTMLElement);

    const exitScorerButton = screen.getByText(/Exit Scorer/i).closest("button");
    fireEvent.click(exitScorerButton as HTMLElement);

    await expectNavigateToDashboard();
  });

  it("should create new scorer when Create Scorer button is clicked", async () => {
    renderApp("/new-scorer");

    const scoringMechanism = screen.getByTestId("scoring-mechanism-0"); // Weighted
    const createScorerButton = screen
      .getByText(/Create Scorer/i)
      .closest("button");

    fireEvent.click(scoringMechanism as HTMLElement);

    fireEvent.click(
      screen.getByText(/Create Scorer/i).closest("button") as HTMLElement
    );

    await waitFor(() =>
      expect(createCommunity).toHaveBeenCalledWith({
        name: "Gitcoin Airdrop",
        description:
          "This airdrop is for participants of the Gitcoin hackathon",
        use_case: "Airdrop Protection",
        rule: "LIFO",
        scorer: "WEIGHTED",
      })
    );

    await expectNavigateToDashboard();
  });
});
