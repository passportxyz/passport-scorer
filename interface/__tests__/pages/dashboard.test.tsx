import { render } from "@testing-library/react";
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
});
