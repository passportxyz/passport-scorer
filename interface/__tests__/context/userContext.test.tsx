import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { UserProvider, UserContext } from "../../context/userContext";
import { useConnectWallet } from "@web3-onboard/react";
import { EIP1193Provider, WalletState } from "@web3-onboard/core";
import { initiateSIWE } from "../../utils/siwe";
import { authenticate } from "../../utils/account-requests";

const mockWallet: WalletState = {
  accounts: [
    {
      address: "0xc79abb54e4824cdb65c71f2eeb2d7f2dasds1fb8",
      ens: null,
      uns: null,
      balance: {
        ETH: "0.000093861007065",
      },
    },
  ],
  chains: [
    {
      namespace: "evm",
      id: "0x1",
    },
  ],
  icon: "",
  label: "Meatmask",
  provider: {} as EIP1193Provider,
};

const connect = jest.fn();

jest.mock("@web3-onboard/react", () => ({
  useConnectWallet: jest.fn(),
  init: jest.fn(),
  connect: jest.fn(),
}));

jest.mock("../../utils/siwe");
jest.mock("../../utils/account-requests");

const mockComponent = () => (
  <UserProvider>
    <UserContext.Consumer>
      {(value) => (
        <div>
          <button onClick={value.login}>Login</button>
          <span data-testid="connected">{value.connected.toString()}</span>
          <span data-testid="authenticationError">
            {value.authenticationError.toString()}
          </span>
          <span data-testid="authenticating">
            {value.authenticating.toString()}
          </span>
          <span data-testid="loginComplete">
            {value.loginComplete.toString()}
          </span>
        </div>
      )}
    </UserContext.Consumer>
  </UserProvider>
)

describe("UserProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  it("renders with initial state values", async () => {
    (useConnectWallet as jest.Mock).mockReturnValue([
      { wallet: null },
      connect,
    ]);
    render(
      mockComponent()
    );


    expect(screen.getByTestId("connected")).toHaveTextContent("false");
    expect(screen.getByTestId("authenticationError")).toHaveTextContent(
      "false"
    );
    expect(screen.getByTestId("authenticating")).toHaveTextContent("false");
    expect(screen.getByTestId("loginComplete")).toHaveTextContent("false");
  });

  it("logs in a user", async () => {
    const connect = jest.fn().mockResolvedValue([mockWallet]);
    (useConnectWallet as jest.Mock).mockReturnValue([
      { wallet: mockWallet },
      connect,
    ]);

    (initiateSIWE as jest.Mock).mockResolvedValue({
      siweMessage: {},
      signature: "signature",
    });
    (authenticate as jest.Mock).mockResolvedValue({
      access: "token"
    })

    render(
      mockComponent()
    );

    screen.getByText("Login").click();

    await waitFor(async () => {
      expect(screen.getByTestId("connected")).toHaveTextContent("true");
      expect(screen.getByTestId("authenticationError")).toHaveTextContent(
        "false"
      );
      expect(screen.getByTestId("authenticating")).toHaveTextContent("false");
      expect(screen.getByTestId("loginComplete")).toHaveTextContent("true");
    });
  });
  it("logs out a user", async () => {
    (initiateSIWE as jest.Mock).mockResolvedValue({
      siweMessage: {},
      signature: "signature",
    });
    const connect = jest.fn().mockResolvedValue([mockWallet]);
    (useConnectWallet as jest.Mock).mockReturnValue([
      { wallet: mockWallet },
      connect,
    ]);


    const { rerender } = render(
      mockComponent()
    );

    // click the login button
    screen.getByText("Login").click();

    (useConnectWallet as jest.Mock).mockReturnValue([
      { wallet: null },
      connect,
    ]);

    rerender(mockComponent());
    await waitFor(async () => {
      expect(screen.getByTestId("connected")).toHaveTextContent("false");
      expect(screen.getByTestId("authenticationError")).toHaveTextContent(
        "false"
      );
      expect(screen.getByTestId("loginComplete")).toHaveTextContent("false");
    });
  });
  it("resets state if user rejects signature", async () => {
    const connect = jest.fn().mockResolvedValue([mockWallet]);
    (useConnectWallet as jest.Mock).mockReturnValue([
      { wallet: mockWallet },
      connect,
    ]);

    (initiateSIWE as jest.Mock).mockRejectedValue({
      detail: "User rejected signature",
    });


    render(
      mockComponent()
    );

    // click the login button
    screen.getByText("Login").click();
    expect(screen.getByTestId("connected")).toHaveTextContent("false");
    expect(screen.getByTestId("loginComplete")).toHaveTextContent("false");
  });
});
