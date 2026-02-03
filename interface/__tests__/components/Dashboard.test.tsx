import { screen, waitFor } from "@testing-library/react";
import { renderApp } from "../../__test-fixtures__/appHelpers";

describe("Dashboard", () => {
  it("should render the correct dashboard tab with navigation menu", async () => {
    renderApp("/dashboard/api-keys");

    const activeTab = screen.getByTestId("api-keys-tab");
    const notActiveTab = screen.getByTestId("scorer-tab");
    await waitFor(async () => {
      expect(activeTab).toHaveClass(
        "flex w-full items-center justify-start rounded-md px-3 py-2 text-foreground border border-border bg-background"
      );
      expect(notActiveTab).toHaveClass(
        "flex w-full items-center justify-start rounded-md px-3 py-2 text-foreground mb-2"
      );
    });
  });
});
