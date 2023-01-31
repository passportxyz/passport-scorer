import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import APIKeyList from "../../components/APIKeyList";
import { getApiKeys, createApiKey } from "../../utils/account-requests";

jest.mock("../../utils/account-requests.ts", () => ({
  getApiKeys: jest.fn(),
  createApiKey: jest.fn(),
}));

describe("APIKeyList", () => {
  beforeEach(() => {
    (getApiKeys as jest.Mock).mockResolvedValue([
      { name: "key1", prefix: "safasfasdf" },
      { name: "key2", prefix: "asdfasf" },
    ]);
    (createApiKey as jest.Mock).mockResolvedValue({});
  });
  it("should create an API key", async () => {
    render(<APIKeyList />);

    await waitFor(async () => {
      const modalButton = screen.getByTestId("open-api-key-modal");
      fireEvent.click(modalButton as HTMLElement);
      expect(screen.getByTestId("create-button")).toBeInTheDocument();
      const input = screen.getByTestId("key-name-input");
      fireEvent.change(input, { target: { value: "test" } });
      const createButton = screen.getByTestId("create-button");
      fireEvent.click(createButton as HTMLElement);
      expect(createApiKey).toHaveBeenCalledWith("test");
    });
  });

  it("should render a list of API keys", async () => {
    render(<APIKeyList />);

    await waitFor(async () => {
      expect(screen.getByText("key2")).toBeInTheDocument();
    });
  });
});
