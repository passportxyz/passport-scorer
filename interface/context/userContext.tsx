import { createContext, useEffect, useState } from "react";

import { useConnectWallet } from "@web3-onboard/react";
import { WalletState } from "@web3-onboard/core";
import "../utils/onboard";

import { initiateSIWE } from "../utils/siwe";
import { authenticate, verifyToken } from "../utils/account-requests";

export interface UserState {
  ready: boolean;
  connected: boolean;
  authenticationError: boolean;
  authenticating: boolean;
  loginComplete: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

export const initialState: UserState = {
  connected: false,
  ready: false,
  authenticationError: false,
  authenticating: false,
  loginComplete: false,
  login: async () => {},
  logout: async () => {},
};

enum UserActions {
  CONNECTED = "CONNECTED",
  SET_WEB3_ONBOARD = "SET_WEB3_ONBOARD",
  AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR",
  AUTHENTICATING = "AUTHENTICATING",
  LOGIN_COMPLETED = "LOGIN_COMPLETED",
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
    case UserActions.AUTHENTICATION_ERROR:
      return {
        ...state,
        authenticationError: action.payload,
      };
    case UserActions.AUTHENTICATING:
      return {
        ...state,
        authenticating: action.payload,
      };
    case UserActions.LOGIN_COMPLETED:
      return {
        ...state,
        loginComplete: action.payload,
      };
    default:
      return state;
  }
};

export const UserContext = createContext(initialState);

export const UserProvider = ({ children }: { children: any }) => {
  const [{ wallet }, connect] = useConnectWallet();
  const [connected, setConnected] = useState(false);
  const [ready, setReady] = useState(false);
  const [authenticating, setAuthenticating] = useState(false);
  const [loginComplete, setLoginComplete] = useState(false);
  const [authenticationError, setAuthenticationError] = useState(false);

  const login = async () => {
    connect()
      .then((wallets) => {
        const firstWallet = wallets[0];
        authenticateWithScorerApi(firstWallet);
      })
      .catch((e) => {
        // Indicate error connecting?
      });
  };

  const logout = async () => {
    localStorage.removeItem("access-token");
    localStorage.removeItem("connectedWallets");
    setLoginComplete(false);
    setConnected(false);
  };

  // Restore wallet connection from localStorage
  const setWalletFromLocalStorage = async (): Promise<void> => {
    const previouslyConnectedWallets = JSON.parse(
      // retrieve localstorage state
      window.localStorage.getItem("connectedWallets") || "[]"
    ) as string[];
    const accessToken = window.localStorage.getItem("access-token");
    if (accessToken) {
      try {
        const { expDate } = await verifyToken(accessToken);
        // We want the token to be valid for at least 6 hours
        const minExpirationData = new Date(Date.now() + 1000 * 60 * 60 * 6);
        if (expDate < minExpirationData) {
          window.localStorage.removeItem("access-token");
          return;
        }
      } catch (e) {
        window.localStorage.removeItem("access-token");
        return;
      }
    }
    if (previouslyConnectedWallets?.length) {
      try {
        await connect({
          autoSelect: {
            label: previouslyConnectedWallets[0],
            disableModals: true,
          },
        });

        setConnected(true);
      } catch (e) {
        // remove localstorage state
        window.localStorage.removeItem("connectedWallets");
        localStorage.removeItem("access-token");
      }
    }
  };

  const authenticateWithScorerApi = async (wallet: WalletState) => {
    try {
      setAuthenticating(true);
      const { siweMessage, signature } = await initiateSIWE(wallet);
      const tokens = await authenticate(siweMessage, signature);

      window.localStorage.setItem(
        "connectedWallets",
        JSON.stringify([wallet.label])
      );

      // store JWT access token in LocalStorage
      localStorage.setItem("access-token", tokens.access);

      setConnected(true);
      setAuthenticating(false);
      setLoginComplete(true);
    } catch (e) {
      setAuthenticationError(true);
      setAuthenticating(false);
    }
  };

  // On load check localstorage for loggedin credentials
  useEffect(() => {
    (async () => {
      try {
        await setWalletFromLocalStorage();
      } finally {
        setReady(true);
      }
    })();
  }, []);

  // Used to listen to disconnect event from web3Onboard widget
  useEffect(() => {
    if (!wallet && connected) {
      logout();
    }
  }, [wallet, connected]);

  return (
    <UserContext.Provider
      value={{
        ready,
        connected,
        authenticating,
        loginComplete,
        authenticationError,
        login,
        logout,
      }}
    >
      {children}
    </UserContext.Provider>
  );
};
