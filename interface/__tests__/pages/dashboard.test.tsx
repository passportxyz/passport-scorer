import { fireEvent, render } from "@testing-library/react";
import Dashboard from "../../pages/dashboard";

jest.mock("@rainbow-me/rainbowkit", () => {
  return {
    ConnectButton: jest.fn(() => <div>ConnectButton</div>),
  };
});

describe("Dashboard", () => {
  it("should render the dashboard", () => {
    render(<Dashboard authenticationStatus="authenticated" />);
  });
  it("should show API key content when tab is clicked", () => {
    const { getByText } = render(
      <Dashboard authenticationStatus="authenticated" />
    );
    const apiKeyTab = getByText("API Keys");
    fireEvent.click(apiKeyTab);
    expect(getByText("Create a key")).toBeInTheDocument();
  });
});
