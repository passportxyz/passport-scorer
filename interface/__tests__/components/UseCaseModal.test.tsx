import React from "react";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import UseCaseModal from "../../components/UseCaseModal";
import { Community } from "../../utils/account-requests";

jest.mock("next/router", () => require("next-router-mock"));
jest.mock("react-router-dom", () => ({
  useNavigate: jest.fn(),
}));

const existingScorers = [
  {
    name: "Existing 1",
    description: "asdfasdf",
    id: 7,
    created_at: "2023-03-20T20:27:02.425Z",
    use_case: "Airdrop Protection",
  },
  {
    name: "Existing 2",
    description: "a",
    id: 8,
    created_at: "2023-03-20T22:19:22.363Z",
    use_case: "Airdrop Protection",
  },
] as Community[];

const noop = () => {};
const refreshCommunities = jest.fn();

describe("UseCaseModal", () => {
  it("should display the creation modal for scorer", async () => {
    render(
      <UseCaseModal
        existingScorers={existingScorers}
        isOpen={true}
        onClose={noop}
        refreshCommunities={refreshCommunities}
      />
    );

    expect(screen.getByTestId("use-case-name")).toBeInTheDocument();
    expect(screen.getByTestId("use-case-name-input")).toBeInTheDocument();
    expect(
      screen.getByTestId("use-case-description-input")
    ).toBeInTheDocument();
    expect(screen.getByTestId("use-case-threshold-input")).toBeInTheDocument();
  });

  it("continue button should only be enabled when a use case is selected", async () => {
    render(
      <UseCaseModal
        existingScorers={existingScorers}
        isOpen={true}
        onClose={noop}
        refreshCommunities={refreshCommunities}
      />
    );
    const useCaseSelect = screen.getByTestId(
      "use-case-name"
    ) as HTMLSelectElement;

    // Wait for step 2 UI to be present
    await waitFor(() => {
      expect(screen.getByTestId("use-case-name-input")).toBeInTheDocument();
    });
    const thresholdInput = screen.getByTestId("use-case-threshold-input");
    const continueBtn = screen.getByText(/Continue/i).closest("button");
    // Fill in required fields first
    const nameInput = screen.getByTestId("use-case-name-input");
    const descriptionInput = screen.getByTestId("use-case-description-input");
    fireEvent.change(nameInput, { target: { value: "Unique Test Name 123" } });
    fireEvent.change(descriptionInput, {
      target: { value: "This is my use case description" },
    });

    // Now set a valid threshold
    fireEvent.change(thresholdInput, { target: { value: "10" } });

    // Wait for all state updates before asserting
    await waitFor(() => {
      expect(continueBtn).toBeDisabled();
    });

    // Change the use case selection
    fireEvent.change(useCaseSelect, {
      target: { value: useCaseSelect.options[1].value },
    });

    await waitFor(() => {
      expect(continueBtn).not.toBeDisabled();
    });
  });

  it("continue button should only be enabled when a use case name and description is filled", async () => {
    render(
      <UseCaseModal
        existingScorers={existingScorers}
        isOpen={true}
        onClose={noop}
        refreshCommunities={refreshCommunities}
      />
    );

    const useCaseSelect = screen.getByTestId(
      "use-case-name"
    ) as HTMLSelectElement;

    const nameInput = screen.getByTestId("use-case-name-input");
    const descriptionInput = screen.getByTestId("use-case-description-input");
    const secondContinueButton = screen
      .getByText(/Continue/i)
      .closest("button");

    expect(secondContinueButton).toBeDisabled();

    fireEvent.change(useCaseSelect, {
      target: { value: useCaseSelect.options[1].value },
    });
    fireEvent.change(nameInput, { target: { value: "My Use Case" } });
    fireEvent.change(descriptionInput, {
      target: { value: "This is my use case description" },
    });

    expect(secondContinueButton).toBeEnabled();
  });

  it("should show duplication error if scorer has duplicate name", async () => {
    render(
      <UseCaseModal
        existingScorers={existingScorers}
        isOpen={true}
        onClose={noop}
        refreshCommunities={refreshCommunities}
      />
    );
    const useCaseSelect = screen.getByTestId(
      "use-case-name"
    ) as HTMLSelectElement;

    const nameInput = screen.getByTestId("use-case-name-input");
    const descriptionInput = screen.getByTestId("use-case-description-input");
    const secondContinueButton = screen
      .getByText(/Continue/i)
      .closest("button");

    expect(secondContinueButton).toBeDisabled();

    fireEvent.change(useCaseSelect, {
      target: { value: useCaseSelect.options[1].value },
    });
    fireEvent.change(nameInput, { target: { value: "Existing 2" } });
    fireEvent.change(descriptionInput, {
      target: { value: "This is my use case description" },
    });

    expect(secondContinueButton).toBeEnabled();

    if (!secondContinueButton) throw new Error("Button not found");
    fireEvent.click(secondContinueButton);

    await waitFor(() => {
      expect(
        screen.getByText("A scorer with this name already exists")
      ).toBeInTheDocument();
    });
  });

  it("should validate threshold input", async () => {
    render(
      <UseCaseModal
        existingScorers={existingScorers}
        isOpen={true}
        onClose={noop}
        refreshCommunities={refreshCommunities}
      />
    );
    const useCaseSelect = screen.getByTestId(
      "use-case-name"
    ) as HTMLSelectElement;

    // Wait for step 2 UI to be present
    await waitFor(() => {
      expect(screen.getByTestId("use-case-name-input")).toBeInTheDocument();
    });
    const thresholdInput = screen.getByTestId("use-case-threshold-input");
    const continueBtn = screen.getByText(/Continue/i).closest("button");
    // Fill in required fields first
    const nameInput = screen.getByTestId("use-case-name-input");
    const descriptionInput = screen.getByTestId("use-case-description-input");
    fireEvent.change(useCaseSelect, {
      target: { value: useCaseSelect.options[1].value },
    });
    fireEvent.change(nameInput, { target: { value: "Unique Test Name 123" } });
    fireEvent.change(descriptionInput, {
      target: { value: "This is my use case description" },
    });
    // Set invalid threshold
    fireEvent.change(thresholdInput, { target: { value: "0" } });

    // Check that the button is initially disabled
    await waitFor(() => {
      expect(continueBtn).toBeDisabled();
    });

    // Now set a valid threshold
    fireEvent.change(thresholdInput, { target: { value: "10" } });
    // Wait for all state updates before asserting
    await waitFor(() => {
      expect(screen.queryByTestId("threshold-error")).toBeNull();
      expect(continueBtn).not.toBeDisabled();
    });
  });
});
