import React from "react";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { ApiKeyList } from "../../components/APIKeyList";
import { getApiKeys, createApiKey } from "../../utils/account-requests";

jest.mock("../../utils/account-requests.ts", () => ({
  getApiKeys: jest.fn(),
  createApiKey: jest.fn(),
}));

describe("APIKeyList", () => {
  beforeEach(() => {
    (getApiKeys as jest.Mock).mockResolvedValue(["key1", "key2"]);
    (createApiKey as jest.Mock).mockResolvedValue({});
  });
  it("should have button that creates an API key", async () => {
    act(() => {
      render(<ApiKeyList />);
    });

    const createButton = await screen.getByTestId("create-button");
    await waitFor(() => {
      expect(createButton).toBeInTheDocument();
    });

    await fireEvent.click(createButton as HTMLElement);
    await waitFor(() => {
      expect(createApiKey).toHaveBeenCalled();
    });
  });

  it("should render a list of API keys", async () => {
    act(() => {
      render(<ApiKeyList />);
    });

    await waitFor(async () => {
      expect(await screen.getByText("API Key #2")).toBeInTheDocument();
    });
  });
});
