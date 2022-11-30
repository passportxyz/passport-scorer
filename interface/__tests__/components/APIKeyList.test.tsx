import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { ApiKeyList } from "../../components/APIKeyList";

global.fetch = jest.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({ test: 100 }),
  })
) as jest.Mock;

describe("APIKeyList", () => {
  it("should have button that creates an API key", async () => {
    render(<ApiKeyList />);
    const createButton = screen.getByTestId("create-button");
    expect(createButton).toBeInTheDocument();

    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    global.Storage.prototype.getItem = jest.fn((key) => "12345") as jest.Mock;
    await fireEvent.click(createButton as HTMLElement);
    expect(global.fetch).toHaveBeenCalledWith(
      `${SCORER_BACKEND}account/api-key`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          AUTHORIZATION: "Bearer 12345",
        },
      }
    );
  });
});
