import React, { useEffect, useMemo, useState } from "react";
import { UserContext } from "../context/userContext";
import { render } from "@testing-library/react";
import { UserState } from "../context/userContext";

jest.mock("@web3-onboard/react", () => ({
  useConnectWallet: jest.fn(),
  init: jest.fn(),
}));
jest.mock("@web3-onboard/core", () => ({
  OnboardAPI: jest.fn(),
  WalletState: jest.fn(),
}));
jest.mock("@web3-onboard/walletconnect", () => jest.fn());
jest.mock("@web3-onboard/coinbase", () => jest.fn());
jest.mock("@web3-onboard/ledger", () => jest.fn());
jest.mock("@web3-onboard/injected-wallets", () => jest.fn());

jest.mock("../utils/onboard");

jest.mock("next/router", () => require("next-router-mock"));

export const makeTestUserContext = (
  initialState?: Partial<UserState>
): UserState => {
  return {
    connected: false,
    authenticationError: false,
    authenticating: false,
    loginComplete: false,
    login: async () => { },
    logout: async () => { },
    setUserWarning: (warning?: string) => { },
    ...initialState,
  };
};

export const renderWithContext = (
  userContext: UserState,
  ui: React.ReactElement<any, string | React.JSXElementConstructor<any>>
) => {
  render(<UserContext.Provider value={userContext}>{ui}</UserContext.Provider>);
};
