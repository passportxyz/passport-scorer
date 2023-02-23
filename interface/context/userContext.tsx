import { createContext, useState, useReducer, useEffect } from "react";

import { useConnectWallet } from "@web3-onboard/react";
import { OnboardAPI, WalletState } from "@web3-onboard/core";
import { initWeb3Onboard } from "../utils/onboard";

import { SiweMessage } from "siwe";

export interface UserState {
  connected: boolean;
  message: string;
  signature: string;
  login: () => Promise<void>;
  logout: (wallet: WalletState) => Promise<void>;
  web3OnBoard?: OnboardAPI;
  userWallet?: WalletState;
}

export const initialState: UserState = {
  connected: false,
  message: "",
  signature: "",
  login: async () => {},
  logout: async (wallet: WalletState) => {},
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
    try {
      await connect();
      dispatch({
        type: UserActions.CONNECTED,
        payload: true,
      })
    } catch (e) {
      console.log(e)
    }
  };

  const logout = async () => {
    await disconnect();
    dispatch({
      type: UserActions.CONNECTED,
      payload: false,
    });
  };

  useEffect(() => {
    if (wallet) {
      dispatch({
        type: UserActions.CONNECTED,
        payload: true,
      })
    } else {
      dispatch({
        type: UserActions.CONNECTED,
        payload: false,
      })
    }
   }, [wallet]);

  // Init onboard to enable hooks
  useEffect((): void => {
    dispatch({
      type: UserActions.SET_WEB3_ONBOARD,
      payload: initWeb3Onboard,
    });
  }, []);

  return (
    <UserContext.Provider value={{ ...state, login, logout }}>
      {children}
    </UserContext.Provider>
  );
};
