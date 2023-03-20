import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import UseCaseModal from "../../components/UseCaseModal";

jest.mock("next/router", () => require("next-router-mock"));

describe("UseCaseModal", () => {
  it("should display a list of use cases", async () => {
    render(<UseCaseModal isOpen={true} onClose={() => {}} />);
    const useCaseItems = screen.getAllByTestId("use-case-item");

    expect(screen.getByText("Select a Use Case")).toBeInTheDocument();
    expect(useCaseItems.length).toBe(4);
  });

  it("continue button should only be enabled when a use case is selected", async () => {
    render(<UseCaseModal isOpen={true} onClose={() => {}} />);

    const useCaseItem = screen.getAllByTestId("use-case-item")[0];
    const continueButton = screen.getByText(/Continue/i).closest("button");

    expect(continueButton).toBeDisabled();

    fireEvent.click(useCaseItem as HTMLElement);

    expect(continueButton).toBeEnabled();
  });

  it.skip("should switch to use case details step when continue button is clicked on first step", async () => {
    render(<UseCaseModal isOpen={true} onClose={() => {}} />);

    const useCaseItem = screen.getAllByTestId("use-case-item")[0];
    const continueButton = screen.getByText(/Continue/i).closest("button");

    fireEvent.click(useCaseItem as HTMLElement);

    fireEvent.click(continueButton as HTMLElement);

    expect(screen.getByText("Use Case Details")).toBeInTheDocument();
  });

  it.skip("continue button should only be enabled when a use case name and description is filled", async () => {
    render(<UseCaseModal isOpen={true} onClose={() => {}} />);

    const useCaseItem = screen.getAllByTestId("use-case-item")[0];
    const firstContinueButton = screen.getByText(/Continue/i).closest("button");

    fireEvent.click(useCaseItem as HTMLElement);

    fireEvent.click(firstContinueButton as HTMLElement);

    const nameInput = screen.getByTestId("use-case-name-input");
    const descriptionInput = screen.getByTestId("use-case-description-input");
    const secondContinueButton = screen
      .getByText(/Continue/i)
      .closest("button");

    expect(secondContinueButton).toBeDisabled();

    fireEvent.change(nameInput, { target: { value: "My Use Case" } });
    fireEvent.change(descriptionInput, {
      target: { value: "This is my use case description" },
    });

    expect(secondContinueButton).toBeEnabled();
  });
});
