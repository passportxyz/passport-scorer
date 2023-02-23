import { createContext, useState, useReducer, useEffect } from "react";

import { useConnectWallet } from "@web3-onboard/react";
import { OnboardAPI, WalletState } from "@web3-onboard/core";
import { initWeb3Onboard } from "../utils/onboard";

import { SiweMessage } from "siwe";
import { ethers } from "ethers";
import { initiateSIWE } from "../utils/siwe";
import { authenticate } from "../utils/account-requests";

const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;

export interface UserState {
  connected: boolean;
  message: string;
  signature: string;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  web3OnBoard?: OnboardAPI;
}

export const initialState: UserState = {
  connected: false,
  message: "",
  signature: "",
  login: async () => {},
  logout: async () => {},
};

enum UserActions {
  CONNECTED = "CONNECTED",
  SET_WEB3_ONBOARD = "SET_WEB3_ONBOARD",
}

const userReducer = (
  state: UserState,
  action: { type: UserActions; payload: any }
) => {
  switch (action.type) {
    case UserActions.CONNECTED:
      return {
        ...state,
        connected: action.payload,
      };
    case UserActions.SET_WEB3_ONBOARD:
      return {
        ...state,
        web3OnBoard: action.payload,
      };
    default:
      return state;
  }
};

export const UserContext = createContext(initialState);

export const UserProvider = ({ children }: { children: any }) => {
  const [state, dispatch] = useReducer(userReducer, initialState);
  const [{ wallet, connecting }, connect, connected, disconnect] = useConnectWallet();

  const login = async () => {
    connect().then((wallets) => {
      const firstWallet = wallets[0]
      authenticateWithScorerApi(firstWallet)
    }).catch((e) => {
      // Indicate error connecting?
    });
  };

  const logout = async () => {
    localStorage.removeItem("access-token");
    localStorage.removeItem("connectedWallets");

    dispatch({
      type: UserActions.CONNECTED,
      payload: false,
    });
  };

  // Restore wallet connection from localStorage
  const setWalletFromLocalStorage = async (): Promise<void> => {
    const previouslyConnectedWallets = JSON.parse(
      // retrieve localstorage state
      window.localStorage.getItem("connectedWallets") || "[]"
    ) as string[];
    if (previouslyConnectedWallets?.length) {
      connect({
        autoSelect: {
          label: previouslyConnectedWallets[0],
          disableModals: true,
        },
      }).catch((e): void => {
        // remove localstorage state
        window.localStorage.removeItem("connectedWallets");
        localStorage.removeItem("access-token");
      }).finally(() => {
        dispatch({
          type: UserActions.CONNECTED,
          payload: true,
        })
      });
    }
  };

  const authenticateWithScorerApi = async (wallet: WalletState) => {
    try {
      const { siweMessage, signature } = await initiateSIWE(wallet)
      const tokens = await authenticate(siweMessage, signature)

      window.localStorage.setItem("connectedWallets", JSON.stringify([wallet.label]));

      // store JWT access token in LocalStorage
      localStorage.setItem("access-token", tokens.access);

      dispatch({
        type: UserActions.CONNECTED,
        payload: true,
      })
    } catch (e) {
      // Indicate error authenticating?
    }
  }

  // On load check localstorage for loggedin credentials
  useEffect((): void => {
    setWalletFromLocalStorage();
  }, []);

  // Init onboard to enable hooks
  useEffect((): void => {
    dispatch({
      type: UserActions.SET_WEB3_ONBOARD,
      payload: initWeb3Onboard,
    });
  }, []);

  // Used to listen to disconnect event from web3Onboard widget
  useEffect(() => {
    if (!wallet && state.connected) {
      logout()
    }
  }, [wallet, state.connected]);

  return (
    <UserContext.Provider value={{ ...state, login, logout }}>
      {children}
    </UserContext.Provider>
  );
};
