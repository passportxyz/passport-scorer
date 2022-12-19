import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Layout } from "../../components/Layout";

// mock header component
jest.mock("../../components/Header", () => {
  // eslint-disable-next-line react/display-name
  return () => <div></div>;
});

// mock next router
jest.mock("next/router", () => ({
  useRouter: () => ({
    pathname: "/dashboard/api-keys",
  }),
}));

describe("Layout", () => {
  it("should render the header", async () => {
    render(<Layout><div></div></Layout>);
    const activeTab = screen.getByTestId("api-keys-tab");
    const notActiveTab = screen.getByTestId("communities-tab");
    await waitFor(async () => {
      expect(activeTab).toHaveClass("font-bold font-blue-darkblue");
      expect(notActiveTab).toHaveClass("text-purple-softpurple");
    });
  });
});