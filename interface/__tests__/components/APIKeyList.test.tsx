import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import APIKeyList, { ApiKeyDisplay } from "../../components/APIKeyList";
import { ApiKeys, getApiKeys } from "../../utils/account-requests";

// @ts-ignore
global.navigator.clipboard = {
  writeText: jest.fn(),
};

jest.mock("../../utils/account-requests.ts", () => ({
  getApiKeys: jest.fn(),
  createApiKey: jest.fn(),
}));

jest.mock("../../components/ApiKeyModals", () => ({
  ApiKeyCreateModal: ({
    onApiKeyCreated,
  }: {
    onApiKeyCreated: (apiKey: ApiKeyDisplay) => void;
  }) => {
    return (
      <div
        onClick={() =>
          onApiKeyCreated({
            id: "1",
            name: "Mock API Key",
            prefix: "1",
            created: "1",
            api_key: "api-key-0",
          })
        }
        data-testid="generate-api-key"
      >
        Generate API Key
      </div>
    );
  },
}));

describe("APIKeyList", () => {
  beforeEach(() => {
    (getApiKeys as jest.Mock).mockResolvedValue([
      { name: "key1", prefix: "safasfasdf" },
      { name: "key2", prefix: "asdfasf" },
    ]);
  });
  it("should initiate creation of an API key", async () => {
    render(<APIKeyList />);
    await waitFor(async () => {
      const modalButton = screen.getByTestId("open-api-key-modal");
      fireEvent.click(modalButton as HTMLElement);
      expect(screen.getByText("Generate API Key")).toBeInTheDocument();
    });
  });

  it("should render a list of API keys", async () => {
    render(<APIKeyList />);

    await waitFor(async () => {
      expect(screen.getByText("key2")).toBeInTheDocument();
    });
  });

  it("should create an API key and allow it to be copied", async () => {
    render(<APIKeyList />);
    await waitFor(async () => {
      const apiKeyBtn = screen.getByTestId("generate-api-key");
      fireEvent.click(apiKeyBtn as HTMLElement);
    });
    await waitFor(async () => {
      expect(screen.getByText("Mock API Key")).toBeInTheDocument();
      expect(screen.getByText("api-key-0")).toBeInTheDocument();
      expect(screen.getByTestId("copy-api-key")).toBeInTheDocument();
    });
  });
  it("should hide api key after it is copied", async () => {
    render(<APIKeyList />);
    await waitFor(async () => {
      const apiKeyBtn = screen.getByTestId("generate-api-key");
      fireEvent.click(apiKeyBtn as HTMLElement);
    });
    await waitFor(async () => {
      const copyBtn = screen.getByTestId("copy-api-key");
      fireEvent.click(copyBtn as HTMLElement);
    });

    await waitFor(async () => {
      expect(screen.queryByText("api-key-0")).not.toBeInTheDocument();
      expect(screen.getByText("Copied!")).toBeInTheDocument();
    });
  });
});
