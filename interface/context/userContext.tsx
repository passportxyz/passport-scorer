import { createContext, useReducer, useEffect } from "react";

import { useConnectWallet } from "@web3-onboard/react";
import { WalletState } from "@web3-onboard/core";
import "../utils/onboard";

import { initiateSIWE } from "../utils/siwe";
import { authenticate, verifyToken } from "../utils/account-requests";

export interface UserState {
  connected: boolean;
  authenticationError: boolean;
  authenticating: boolean;
  loginComplete: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

export const initialState: UserState = {
  connected: false,
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
  const [state, dispatch] = useReducer(userReducer, initialState);
  const [{ wallet }, connect] = useConnectWallet();

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
    dispatch({
      type: UserActions.LOGIN_COMPLETED,
      payload: false,
    });
    dispatch({
      type: UserActions.CONNECTED,
      payload: false,
    });
  };

  // Restore wallet connection from localStorage
  const setWalletFromLocalStorage = async (): Promise<void> => {
    console.log("setWalletFromLocalStorage", 1);
    const previouslyConnectedWallets = JSON.parse(
      // retrieve localstorage state
      window.localStorage.getItem("connectedWallets") || "[]"
    ) as string[];
    console.log("setWalletFromLocalStorage", 2);
    const accessToken = window.localStorage.getItem("access-token");
    console.log({ accessToken });
    if (accessToken) {
      try {
        const { expDate } = await verifyToken(accessToken);
        // We want the token to be valid for at least 24 hours
        const minExpirationData = new Date(Date.now() + 1000 * 60 * 60 * 24)
        if (expDate < minExpirationData) {
          window.localStorage.removeItem("access-token");
        }
      } catch (e) {
        window.localStorage.removeItem("access-token");
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

        dispatch({
          type: UserActions.CONNECTED,
          payload: true,
        });
      } catch (e) {
        // remove localstorage state
        window.localStorage.removeItem("connectedWallets");
        localStorage.removeItem("access-token");
      }
    }
  };

  const authenticateWithScorerApi = async (wallet: WalletState) => {
    console.log("authenticateWithScorerApi", 1);
    try {
      dispatch({
        type: UserActions.AUTHENTICATING,
        payload: true,
      });
      console.log("authenticateWithScorerApi", 2);
      const { siweMessage, signature } = await initiateSIWE(wallet);
      console.log("authenticateWithScorerApi", 3);
      const tokens = await authenticate(siweMessage, signature);

      console.log("authenticateWithScorerApi", 4);
      window.localStorage.setItem(
        "connectedWallets",
        JSON.stringify([wallet.label])
      );
      console.log("authenticateWithScorerApi", 5);

      // store JWT access token in LocalStorage
      localStorage.setItem("access-token", tokens.access);

      dispatch({
        type: UserActions.CONNECTED,
        payload: true,
      });
      dispatch({
        type: UserActions.AUTHENTICATING,
        payload: false,
      });
      dispatch({
        type: UserActions.LOGIN_COMPLETED,
        payload: true,
      });
    } catch (e) {
      dispatch({
        type: UserActions.AUTHENTICATION_ERROR,
        payload: true,
      });
      dispatch({
        type: UserActions.AUTHENTICATING,
        payload: false,
      });
    }
  };

  // On load check localstorage for loggedin credentials
  useEffect((): void => {
    setWalletFromLocalStorage();
  }, []);

  // Used to listen to disconnect event from web3Onboard widget
  useEffect(() => {
    if (!wallet && state.connected) {
      logout();
    }
  }, [wallet, state.connected]);

  return (
    <UserContext.Provider value={{ ...state, login, logout }}>
      {children}
    </UserContext.Provider>
  );
};
