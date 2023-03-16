import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApiKeyCreateModal } from "../../components/ApiKeyModals";
import { ApiKeys } from "../../utils/account-requests";
import { createApiKey } from "../../utils/account-requests";

jest.mock("../../utils/account-requests.ts", () => ({
  createApiKey: jest.fn(),
}));

describe("APIKeyCreateModal", () => {
  it("should render", () => {
    render(
      <ApiKeyCreateModal
        isOpen={true}
        onClose={() => {}}
        onCreateApiKey={function (keyName: ApiKeys["name"]): void {
          throw new Error("Function not implemented.");
        }}
      />
    );
    expect(screen.getByText("Generate API Key")).toBeInTheDocument();
  });

  it("should call createApiKey when the create button is clicked", async () => {
    const value = "test";
    const createResponse = { name: "test" };

    (createApiKey as jest.Mock).mockResolvedValue(createResponse);

    render(
      <ApiKeyCreateModal
        isOpen={true}
        onClose={() => {}}
        onCreateApiKey={createApiKey}
      />
    );
    const input = screen.getByTestId("key-name-input");
    fireEvent.change(input, { target: { value } });
    const createButton = screen.getByText("Create");
    fireEvent.click(createButton as HTMLElement);
    await waitFor(() => {
      expect(createApiKey).toHaveBeenCalledWith(value);
    });
  });
});
